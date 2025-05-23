import os
from datetime import datetime, timezone
from typing import Literal

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode


#Tool that returns current time in UTC ISO-8601 format
@tool
def get_current_time() -> dict:
    """Return the current UTC time in ISO‑8601 format.
    Example → {"utc": "2025‑05‑21T06:42:00Z"}"""
    now = datetime.now(timezone.utc)
    return {"utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


#Set up the Ollama model
def setup_model():
    model = ChatOllama(  
        model="llama3.2",#supports function calling
        temperature=0.2,
        base_url="http://localhost:11434"
    )
    
    tools = [get_current_time]
    return model.bind_tools(tools)

#Decide whether to call tools or end the conversation
def should_continue(state: MessagesState) -> Literal["tools", "end"]:
    messages = state['messages']
    last_message = messages[-1]
    
    #If the model wants to call a tool
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"

    return "end"

#Main function that calls the model with current message state
def call_model(state: MessagesState):
    messages = state['messages']

        #Adding system message to try to control behavior
    system_message = SystemMessage(content="""
You are a friendly assistant. 
IMPORTANT: Use the get_current_time tool ONLY when the user explicitly asks about time.
Time keywords: "время", "час", "сколько времени", "который час", "time", "utc", "what time".
In all other cases, just answer user questions without using tools.
""")
    
    #Add system message only if it's not already there
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [system_message] + messages
    
    model_with_tools = setup_model()
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


#Create state graph to manage agent and tools interaction
def create_graph():
    workflow = StateGraph(MessagesState)
    
    #Add nodes - agent (our model) and tools
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode([get_current_time]))
    
    #Set where execution starts
    workflow.set_entry_point("agent")

    #If agent needs tools, call them, otherwise end conversation  
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": "__end__"}
    )
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


#Test the bot locally in console
def test_locally():
    print("Bot started, write something to it")
    print("Try asking: 'What time is it now?' or 'Сколько сейчас времени?")
    
    app = create_graph()
    config = {"configurable": {"thread_id": "test"}}
    
    while True:
        try:
            user_msg = input("\nYou: ")
            if user_msg.lower() in ['quit', 'выход', 'exit']:
                break
                
            result = app.invoke(
                {"messages": [HumanMessage(content=user_msg)]},
                config=config
            )
            
            print(f"Bot: {result['messages'][-1].content}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    print("Goodbye!")


#Main graph for development (langgraph dev)
graph = create_graph()

if __name__ == "__main__":
    test_locally()