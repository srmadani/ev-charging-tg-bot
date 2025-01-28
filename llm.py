# llm.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
import datetime
import sqlite3
from reg import DATABASE_NAME, get_user_conversation_id, start_new_conversation # Import database name and conversation functions

# --- Initialize LLM and Langchain Graph ---
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")

workflow = StateGraph(state_schema=MessagesState)

def call_model(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

memory = MemorySaver()
app_langchain = workflow.compile(checkpointer=memory)


async def log_message_to_db(conversation_id, sender_type, message_text):
    """Logs a message to the messages table in the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    now = datetime.datetime.now()
    cursor.execute(
        "INSERT INTO messages (conversation_id, sender_type, message_text, message_time) VALUES (?, ?, ?, ?)",
        (conversation_id, sender_type, message_text, now)
    )
    conn.commit()
    conn.close()


async def get_llm_response(user_input: str, user_id: str) -> str:
    """
    Gets the LLM's response for a given user input, using memory based on user_id, and logs messages.

    Args:
        user_input: The text input from the user.
        user_id: The Telegram user ID, used as thread_id for memory and conversation ID.

    Returns:
        The LLM's text response.
    """
    conversation_id = await get_user_conversation_id(user_id)
    if not conversation_id:
        conversation_id = await start_new_conversation(user_id) # Start new conversation if none exists

    await log_message_to_db(conversation_id, 'user', user_input) # Log user message

    config = {"configurable": {"thread_id": str(user_id)}} # Thread ID for memory
    input_messages = [HumanMessage(user_input)]
    output = app_langchain.invoke({"messages": input_messages}, config)
    llm_response_message = output["messages"][-1]
    llm_response_text = llm_response_message.content

    await log_message_to_db(conversation_id, 'llm', llm_response_text) # Log LLM response

    return llm_response_text