import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from dotenv import load_dotenv
from neo4j import GraphDatabase
import google.generativeai as genai

# Load environment variables
load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize FastAPI app
app = FastAPI(title="Cricket Graph RAG API")

# CRITICAL: Allow your future frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (Netlify, localhost, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (POST, GET, DELETE, etc.)
    allow_headers=["*"],
)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Database Driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

class QueryRequest(BaseModel):
    query: str

class DeleteRequest(BaseModel):
    confirmation: str

# --- HELPER FUNCTIONS ---
def get_graph_context(query: str):
    extraction_prompt = f"Extract a comma-separated list of the 2 most important proper nouns or entities from this question: '{query}'. Return ONLY the comma-separated list, no other text."
    try:
        extraction_response = model.generate_content(extraction_prompt)
        entities = [e.strip() for e in extraction_response.text.split(',')]
    except Exception:
        return []
    
    context_paths = []
    with driver.session() as session:
        for entity in entities:
            cypher_query = """
            MATCH (n)-[r]->(m) 
            WHERE toLower(n.name) CONTAINS toLower($entity) OR toLower(m.name) CONTAINS toLower($entity)
            RETURN n.name AS source, type(r) AS relationship, m.name AS target LIMIT 5
            """
            result = session.run(cypher_query, entity=entity)
            for record in result:
                context_paths.append(f"{record['source']} -> {record['relationship']} -> {record['target']}")
    
    return list(set(context_paths))

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Backend is running perfectly!"}

# 1. ADD DATA (Upload PDF -> Extract -> Neo4j)
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    reader = PdfReader(file.file)
    text_content = "".join([page.extract_text() + "\n" for page in reader.pages if page.extract_text()])
    
    prompt = f"""
    Analyze the text and extract entities and relationships.
    Format as strictly valid JSON without markdown tags:
    {{
      "nodes": [{{"id": "node_id", "label": "Label", "name": "Display Name"}}],
      "relationships": [{{"source": "source_id", "target": "target_id", "type": "RELATION"}}]
    }}
    Text: {text_content[:5000]}
    """
    
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    graph_data = json.loads(response.text)
    
    with driver.session() as session:
        for node in graph_data.get("nodes", []):
            label = node.get("label", "Entity").replace(" ", "_")
            session.run(f"MERGE (n:{label} {{id: $id}}) ON CREATE SET n.name = $name", id=node["id"], name=node["name"])
            
        for rel in graph_data.get("relationships", []):
            rel_type = rel.get("type", "RELATED_TO").replace(" ", "_").upper()
            session.run(f"""
            MATCH (a {{id: $source}}), (b {{id: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
            """, source=rel["source"], target=rel["target"])
            
    return {"message": f"Successfully added {len(graph_data.get('nodes', []))} nodes and {len(graph_data.get('relationships', []))} relationships."}

# 2. DELETE DATA
@app.delete("/delete")
async def clear_database(req: DeleteRequest):
    if req.confirmation.lower() != "confirm":
        raise HTTPException(status_code=400, detail="You must pass confirmation='confirm'.")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    return {"message": "Database completely wiped."}

# 3. RETRIEVE CONTEXT ONLY
@app.post("/retrieve")
async def retrieve_data(req: QueryRequest):
    context = get_graph_context(req.query)
    return {"context": context}

# 4. FULL GRAPH RAG RESPONSE
@app.post("/ask")
async def generate_rag_response(req: QueryRequest):
    context = get_graph_context(req.query)
    if not context:
        return {"answer": "I couldn't find any information about that in the database.", "graph_context": []}
    
    context_string = "\n".join(context)
    prompt = f"""
    You are a helpful assistant. Use ONLY the provided Graph Database Context to answer the user's question.
    Graph Database Context:
    {context_string}
    
    User Question: {req.query}
    """
    response = model.generate_content(prompt)
    return {"answer": response.text, "graph_context": context}