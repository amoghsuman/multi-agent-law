# Agents - Legal Team
import os
import streamlit as st
import tempfile
from agno.agent import Agent
from agno.models.google import Gemini
from agno.embedder.google import GeminiEmbedder
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.vectordb.chroma import ChromaDb
from agno.document.chunking.document import DocumentChunking

# --------------------------- Streamlit UI Setup ---------------------------

st.set_page_config(page_title="AI Legal Team Agents", page_icon="⚖️", layout="wide")

st.markdown("<h1 style='text-align: center; color: #3e8e41;'>👨‍⚖️ AI Legal Team Agents</h1>", unsafe_allow_html=True)

st.markdown("""
    <div style='text-align: center; font-size: 18px; color: #4B0082;'>
        Upload your legal document and let the <b>AI LegalAdvisor</b>, <b>AI ContractsAnalyst</b>, 
        <b>AI LegalStrategist</b>, and <b>AI Team Lead</b> do the work for you. You can also ask 
        questions in between for enhanced collaboration and insights.
    </div>
""", unsafe_allow_html=True)

# --------------------------- Session State Initialization ---------------------------

if "vector_db" not in st.session_state:
    st.session_state.vector_db = ChromaDb(
        collection="law", path="tmp/chromadb", persistent_client=True, embedder=GeminiEmbedder()
    )

if "knowledge_base" not in st.session_state:
    st.session_state.knowledge_base = None

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# --------------------------- Sidebar Config ---------------------------

with st.sidebar:
    st.header("Configuration")

    # Securely load the Google Gemini API key from Streamlit secrets
    api_key = st.secrets.get("GOOGLE_API_KEY", None)

    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        st.success("API key loaded from secrets!")
    else:
        st.error("Missing Google API Key in Streamlit secrets!")

    # Document chunking parameters
    chunk_size_in = st.number_input("Chunk Size", min_value=1, max_value=5000, value=1000)
    overlap_in = st.number_input("Overlap", min_value=1, max_value=1000, value=200)

    st.header("📄 Document Upload")
    uploaded_file = st.file_uploader("Upload a Legal Document (PDF)", type=["pdf"])

    if uploaded_file:
        if uploaded_file.name not in st.session_state.processed_files:
            with st.spinner("Processing document..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_path = temp_file.name

                    st.session_state.knowledge_base = PDFKnowledgeBase(
                        path=temp_path,
                        vector_db=st.session_state.vector_db,
                        reader=PDFReader(),
                        chunking_strategy=DocumentChunking(chunk_size=chunk_size_in, overlap=overlap_in)
                    )

                    st.session_state.knowledge_base.load(recreate=True, upsert=True)
                    st.session_state.processed_files.add(uploaded_file.name)

                    st.success("✅ Document processed and stored in knowledge base!")

                except Exception as e:
                    st.error(f"Error processing document: {e}")

# --------------------------- Agent Initialization ---------------------------

if st.session_state.knowledge_base:
    legal_researcher = Agent(
        name="LegalAdvisor",
        model=Gemini(id="gemini-2.0-flash-exp"),
        knowledge=st.session_state.knowledge_base,
        search_knowledge=True,
        description="Finds and cites relevant legal cases, regulations, and precedents.",
        instructions=[
            "Extract all available data from the knowledge base and search for legal cases, regulations, and citations.",
            "If needed, use DuckDuckGo for additional legal references.",
            "Always provide source references in your answers."
        ],
        tools=[DuckDuckGoTools()],
        show_tool_calls=True,
        markdown=True
    )

    contract_analyst = Agent(
        name="ContractAnalyst",
        model=Gemini(id="gemini-2.0-flash-exp"),
        knowledge=st.session_state.knowledge_base,
        search_knowledge=True,
        description="Identifies key clauses, risks, and obligations in contracts.",
        instructions=[
            "Extract all available data from the knowledge base and analyze the contract for key clauses, obligations, and potential ambiguities.",
            "Reference specific sections of the contract where possible."
        ],
        show_tool_calls=True,
        markdown=True
    )

    legal_strategist = Agent(
        name="LegalStrategist",
        model=Gemini(id="gemini-2.0-flash-exp"),
        knowledge=st.session_state.knowledge_base,
        search_knowledge=True,
        description="Provides strategic legal recommendations and risk assessment.",
        instructions=[
            "Using all data from the knowledge base, assess the contract for legal risks and opportunities.",
            "Provide actionable recommendations and ensure compliance with applicable laws."
        ],
        show_tool_calls=True,
        markdown=True
    )

    team_lead = Agent(
        name="teamlead",
        model=Gemini(id="gemini-2.0-flash-exp"),
        description="Integrates insights from all agents into a comprehensive report.",
        instructions=[
            "Combine and summarize all insights provided by the Legal Researcher, Contract Analyst, and Legal Strategist. "
            "Ensure the final report includes references to all relevant sections from the document."
        ],
        show_tool_calls=True,
        markdown=True
    )

    def get_team_response(query):
        research_response = legal_researcher.run(query)
        contract_response = contract_analyst.run(query)
        strategy_response = legal_strategist.run(query)

        final_response = team_lead.run(
            f"Summarize and integrate the following insights:\n\n"
            f"Legal Researcher:\n{research_response}\n\n"
            f"Contract Analyst:\n{contract_response}\n\n"
            f"Legal Strategist:\n{strategy_response}\n\n"
            "Provide a structured legal analysis report that includes key terms, obligations, risks, and recommendations."
        )
        return final_response

# --------------------------- Analysis Panel ---------------------------

if st.session_state.knowledge_base:
    st.header("🔍 Select Analysis Type")
    analysis_type = st.selectbox(
        "Choose Analysis Type:",
        ["Contract Review", "Legal Research", "Risk Assessment", "Compliance Check", "Custom Query"]
    )

    query = None
    if analysis_type == "Custom Query":
        query = st.text_area("Enter your custom legal question:")
    else:
        predefined_queries = {
            "Contract Review": (
                "Analyze this contract using the knowledge base. Identify key terms, obligations, and risks."
            ),
            "Legal Research": (
                "Find relevant legal cases and precedents using the knowledge base."
            ),
            "Risk Assessment": (
                "Identify potential legal risks in the document and cite specific sections."
            ),
            "Compliance Check": (
                "Evaluate this document for compliance with legal regulations and highlight any concerns."
            )
        }
        query = predefined_queries[analysis_type]

    if st.button("Analyze"):
        if not query:
            st.warning("Please enter a query.")
        else:
            with st.spinner("Analyzing..."):
                response = get_team_response(query)

                tabs = st.tabs(["Analysis", "Key Points", "Recommendations"])

                with tabs[0]:
                    st.subheader("📑 Detailed Analysis")
                    st.markdown(response.content if response.content else "No response generated.")

                with tabs[1]:
                    st.subheader("📌 Key Points Summary")
                    summary = team_lead.run(f"Summarize the key legal points from this analysis:\n{response.content}")
                    st.markdown(summary.content if summary.content else "No summary generated.")

                with tabs[2]:
                    st.subheader("📋 Recommendations")
                    recommendations = team_lead.run(f"Provide legal recommendations based on this analysis:\n{response.content}")
                    st.markdown(recommendations.content if recommendations.content else "No recommendations generated.")
