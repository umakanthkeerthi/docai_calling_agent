
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from voice_server.agent.state import TriageState
from voice_server.agent.nodes.retrieval import retrieval_node
from voice_server.agent.nodes.diagnostician import diagnostician_node
from voice_server.agent.nodes.strategist import strategist_node
from voice_server.agent.nodes.emergency import emergency_scan_node

def build_graph():
    workflow = StateGraph(TriageState)
    
    # Add Nodes
    workflow.add_node("emergency_scan", emergency_scan_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("diagnostician", diagnostician_node)
    workflow.add_node("strategist", strategist_node)
    
    # Define Edges
    workflow.set_entry_point("emergency_scan")
    
    def decide_after_scan(state):
        if state.get("triage_decision") == "EMERGENCY":
            return END
        return "retrieval"

    workflow.add_conditional_edges(
        "emergency_scan",
        decide_after_scan,
        {
            END: END,
            "retrieval": "retrieval"
        }
    )
    
    workflow.add_edge("retrieval", "diagnostician")
    workflow.add_edge("diagnostician", "strategist")
    workflow.add_edge("strategist", END)
    
    # Memory
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

agent_graph = build_graph()
