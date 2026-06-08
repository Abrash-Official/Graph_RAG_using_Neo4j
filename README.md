# Graph RAG using Neo4j

### Application Links
- **Endpoint URL**: [https://graph-rag-using-neo4j.onrender.com/docs](https://graph-rag-using-neo4j.onrender.com/docs)
- **Frontend URL**: [https://graph-rag-neo4j.netlify.app/](https://graph-rag-neo4j.netlify.app/)

### Environment Variables (`.env` structure)
To run this application, you need to create a `.env` file and provide the following variables (you can also refer to `.env.example`):
```env
NEO4J_URI=neo4j+s://your-db-id.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password
GEMINI_API_KEY=your_gemini_api_key_here
```

### Dependencies (`requirements.txt` structure)
This project uses the following Python libraries:
```text
fastapi
uvicorn
neo4j
google-generativeai
python-dotenv
pypdf
python-multipart
pydantic
```

### About Neo4j
Neo4j is a powerful Graph Database that stores data as nodes (entities) and relationships (how they are connected), instead of traditional tables. This makes it incredibly good at finding complex connections between data points, which is perfect for Graph RAG applications. 
To set up your database, you can create a free cloud instance at [Neo4j AuraDB](https://console.neo4j.io/). Once created, you will get the URI, username, and password to use in your `.env` file.

### API Endpoints
The backend (`main.py`) provides the following endpoints to interact with the application:

- **`GET /` (Home)**
  A simple health check to confirm that the backend server is up and running.

- **`POST /upload` (Add Data)**
  Upload a PDF file here. The system reads the document, uses AI to extract key entities and how they relate to each other, and saves this map into the Neo4j database.

- **`DELETE /delete` (Delete Data)**
  Wipes all data from the Neo4j database. As a safeguard, you must send `{"confirmation": "confirm"}` in the request to authorize the deletion.

- **`POST /retrieve` (Get Context)**
  Submit a question, and the system will find and return the specific connections (graph paths) from the database that are relevant to your question.

- **`POST /ask` (Get Answer)**
  The main Graph RAG feature. Submit a question, and the system fetches the relevant data from Neo4j. It then gives this data to the AI, asking it to answer your question accurately based *only* on the provided information.