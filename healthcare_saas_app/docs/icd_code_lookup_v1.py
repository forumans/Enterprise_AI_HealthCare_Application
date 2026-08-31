import os
import requests
from typing import List, Dict, Any
from typing_extensions import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from dotenv import load_dotenv
load_dotenv()


# Define the Graph State
class AgentState(TypedDict):
    doctor_notes: str                 # Input text from the doctor
    extracted_diagnoses: List[str]    # Core search terms (e.g., ["Type 2 Diabetes", "Low back pain"])
    icd10_results: Dict[str, Any]     # Final mapping of terms to codes

# Node 1: Extract core search-friendly medical keywords
def extract_diagnoses_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert medical billing assistant. Analyze the doctor's note and extract ONLY the foundational "
                   "core diagnosis keywords optimized for a database search index. "
                   "Strip out extra descriptive modifiers like 'uncontrolled', 'severe', 'acute', 'chronic', or 'mild'. "
                   "Example: 'severe acute lower back pain' should be extracted as 'low back pain'. "
                   "Output the core terms as a clean, comma-separated list without any extra conversational text."),
        ("user", "{notes}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"notes": state["doctor_notes"]})
    
    # Split string into a clean Python list
    terms = [term.strip() for term in response.content.split(",") if term.strip()]
    return {"extracted_diagnoses": terms}

# Node 2: Query the NLM API using the optimized keywords
# data[0] = The total number of items found
# data[1] = An array of clean ICD code strings (e.g., ["E11.9"])
# data[3] = An array where each element is itself a nested list of strings 
#       (e.g., [["E11.9", "Type 2 diabetes mellitus without complications"]])
def lookup_icd10_node(state: AgentState) -> Dict[str, Any]:
    results = {}
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    
    for term in state["extracted_diagnoses"]:
        query_params = {
            "terms": term,
            "max": 3,
            "sf": "code,name"
        }
        
        try:
            response = requests.get(url, params=query_params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Check that NLM's 4-part list payload arrived safely
                if isinstance(data, list) and len(data) >= 4:
                    codes_list = data[1]         # Plain list of string codes: ['E11.9']
                    descriptions_list = data[3]  # Nested list: [['E11.9', 'Description Text']]
                    
                    matches = []
                    for i in range(len(codes_list)):
                        code = codes_list[i]
                        raw_desc = descriptions_list[i]
                        
                        # Extract description: NLM puts the text at index 1 inside the nested array
                        if isinstance(raw_desc, list) and len(raw_desc) >= 2:
                            desc_text = raw_desc[1]
                        elif isinstance(raw_desc, list) and len(raw_desc) == 1:
                            desc_text = raw_desc[0]
                        else:
                            desc_text = str(raw_desc)
                            
                        matches.append({
                            "code": str(code), 
                            "description": desc_text
                        })
                        
                    results[term] = matches if matches else [{"code": "N/A", "description": "No matches found"}]
                else:
                    results[term] = [{"code": "ERROR", "description": "Invalid format layout from NLM"}]
            else:
                results[term] = [{"code": "ERROR", "description": f"HTTP status {response.status_code}"}]
        except Exception as e:
            # Captures processing bugs and outputs the trace message safely inside the node dictionary
            results[term] = [{"code": "ERROR", "description": f"Processing Exception: {str(e)}"}]
            
    return {"icd10_results": results}





# Build the LangGraph Workflow
builder = StateGraph(AgentState)
builder.add_node("extractor", extract_diagnoses_node)
builder.add_node("api_lookup", lookup_icd10_node)

builder.add_edge(START, "extractor")
builder.add_edge("extractor", "api_lookup")
builder.add_edge("api_lookup", END)

app = builder.compile()

# Execute Test
if __name__ == "__main__":
    sample_notes = "Patient presents with uncontrolled type 2 diabetes and complains of severe acute lower back pain."
    
    initial_input = {"doctor_notes": sample_notes}
    final_output = app.invoke(initial_input)
    
    print("\n--- Doctor's Notes ---")
    print(final_output["doctor_notes"])
    
    print("\n--- Extracted Medical Terms ---")
    print(final_output["extracted_diagnoses"])
    
    print("\n--- API ICD-10 Recommendations ---")
    for term, codes in final_output["icd10_results"].items():
        print(f"\nResults for '{term}':")
        for match in codes:
            if 'error' in match:
                print(f"  - Error: {match['error']}")
            else:
                print(f"  - [{match['code']}] {match['description']}")
