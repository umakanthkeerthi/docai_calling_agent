
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from voice_server.booking_agent.state import BookingState
from voice_server.booking_agent.nodes.scheduler import scheduler_node

def build_booking_graph():
    """
    Build the booking agent workflow graph.
    """
    workflow = StateGraph(BookingState)
    
    # Add scheduler node
    workflow.add_node("scheduler", scheduler_node)
    
    # Set entry point
    workflow.set_entry_point("scheduler")
    
    # Direct edge to END to wait for user input
    workflow.add_edge("scheduler", END)
    
    # Compile with memory
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# Export the compiled graph
booking_graph = build_booking_graph()
