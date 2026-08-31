import os
import requests
from typing import List, Dict, Any
from typing_extensions import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

# Ensure your OpenAI key is set: os.environ["OPENAI_API_KEY"] = "your-key"
load_dotenv()

# 1. State Definition
class AgentState(TypedDict):
    doctor_notes: str
    extracted_diagnoses: List[str]
    icd10_results: Dict[str, Any]
    final_recommendations: Dict[str, Any]

# Node 1: Extract core search terms
def extract_diagnoses_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert medical billing assistant. Analyze the doctor's note and extract ONLY the foundational "
                   "core diagnosis keywords optimized for a database search index. Strip out 'uncontrolled', 'severe', 'acute'. "
                   "Output as a clean, comma-separated list without any extra text."),
        ("user", "{notes}")
    ])
    chain = prompt | llm
    response = chain.invoke({"notes": state["doctor_notes"]})
    terms = [term.strip() for term in response.content.split(",") if term.strip()]
    return {"extracted_diagnoses": terms}

# Node 2: Fetch candidates from the NLM API
def lookup_icd10_node(state: AgentState) -> Dict[str, Any]:
    results = {}
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    for term in state["extracted_diagnoses"]:
        query_params = {"terms": term, "max": 7, "sf": "code,name"}
        try:
            response = requests.get(url, params=query_params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Check NLM structure layout explicitly
                if isinstance(data, list) and len(data) >= 4:
                    codes_list = data[1]         # Plain list of strings
                    descriptions_list = data[3]  # Nested list of pairs
                    
                    matches = []
                    for i in range(len(codes_list)):
                        code = codes_list[i]
                        raw_desc = descriptions_list[i]
                        
                        # Isolate the clean text string from the nested array pair
                        desc_text = raw_desc[1] if isinstance(raw_desc, list) and len(raw_desc) >= 2 else str(raw_desc)
                        matches.append({"code": str(code), "description": desc_text})
                        
                    results[term] = matches if matches else [{"code": "N/A", "description": "No matches found"}]
                else:
                    results[term] = [{"code": "ERROR", "description": "Invalid API format"}]
            else:
                results[term] = [{"code": "ERROR", "description": f"HTTP {response.status_code}"}]
        except Exception as e:
            results[term] = [{"code": "ERROR", "description": str(e)}]
    return {"icd10_results": results}

# Node 3: Let the LLM pick the single best matching code from the results
def select_best_codes_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    final_picks = {}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a professional medical coder. Review the original Doctor's Notes and select the single "
                   "most accurate ICD-10 code from the provided list of candidates. "
                   "Pay close attention to modifiers like 'uncontrolled' (which maps to hyperglycemia) or specific body regions. "
                   "Output ONLY the selected code and its description in this format: [CODE] Description. "
                   "Do not provide any explanation or extra conversational words."),
        ("user", "Original Doctor's Notes: {notes}\n\nCandidate ICD-10 List: {candidates}")
    ])
    
    chain = prompt | llm
    
    for term, candidates in state["icd10_results"].items():
        # Check if list contains data entries instead of checking a .get() method on the raw list object
        if isinstance(candidates, list) and len(candidates) > 0:
            first_item = candidates[0]
            
            # Safely skip execution if Node 2 flagged a backend issue
            if isinstance(first_item, dict) and first_item.get("code") in ["ERROR", "N/A"]:
                final_picks[term] = f"Skipped: {first_item.get('description')}"
                continue
            
            # Format text cleanly for the LLM
            candidates_text = "\n".join([f"- [{c['code']}] {c['description']}" for c in candidates if 'code' in c])
            response = chain.invoke({"notes": state["doctor_notes"], "candidates": candidates_text})
            final_picks[term] = response.content.strip()
        else:
            final_picks[term] = "No candidate codes returned from lookup node."
            
    return {"final_recommendations": final_picks}

# 3. Build and Link the Complete Graph
builder = StateGraph(AgentState)
builder.add_node("extractor", extract_diagnoses_node)
builder.add_node("api_lookup", lookup_icd10_node)
builder.add_node("final_selector", select_best_codes_node)

builder.add_edge(START, "extractor")
builder.add_edge("extractor", "api_lookup")
builder.add_edge("api_lookup", "final_selector")
builder.add_edge("final_selector", END)

app = builder.compile()

# Execute Final Workflow Pipeline
if __name__ == "__main__":
    sample_notes = "Patient presents with uncontrolled type 2 diabetes and complains of severe acute lower back pain."
    final_output = app.invoke({"doctor_notes": sample_notes})
    
    print("\n💡 AI FINAL SMART RECOMMENDATIONS 💡")
    for term, selection in final_output["final_recommendations"].items():
        print(f"\nTarget Issue: '{term}'")
        print(f"🥇 Selected Best Match: {selection}")
