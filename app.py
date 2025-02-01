import streamlit as st
from together import Together

# Initialize the Together client
client = Together(api_key="874bde375c479480654683abd21050ae0381971860908bc4dd368b282b3fa94b")

# Streamlit app
st.title("DeepSeek Chatbot")

# Initialize chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):  # Display messages with the appropriate role (user/assistant)
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Enter your prompt:"):
    # Add user message to chat history
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Call the Together API to stream the response
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1",
        messages=st.session_state.chat_history,
        max_tokens=500,
        temperature=0.7,
        top_p=0.7,
        top_k=50,
        repetition_penalty=1,
        stop=[""],
        stream=True  # Enable streaming for real-time responses
    )

    # Function to process and remove <think> blocks
    def process_response(response):
        buffer = ""
        in_think_block = False
        
        for token in response:
            if hasattr(token, 'choices') and token.choices:
                content = token.choices[0].delta.content
                if content:
                    buffer += content
                    
                    # Check if we have complete think tags
                    while True:
                        if not in_think_block:
                            think_start = buffer.find('<think>')
                            if think_start >= 0:
                                # Send content before the think tag
                                if think_start > 0:
                                    yield buffer[:think_start]
                                buffer = buffer[think_start:]
                                in_think_block = True
                            else:
                                # No think tag found, send the buffer
                                yield buffer
                                buffer = ""
                                break
                        else:
                            think_end = buffer.find('</think>')
                            if think_end >= 0:
                                # Remove the think block and continue processing
                                buffer = buffer[think_end + 8:]  # 8 is length of '</think>'
                                in_think_block = False
                            else:
                                break
        
        # Handle any remaining content
        if buffer and not in_think_block:
            yield buffer

    # Stream the response and remove <think> blocks
    with st.chat_message("assistant"):
        response_placeholder = st.empty()  # Placeholder to update the response dynamically
        full_response = ""
        for chunk in process_response(response):
            full_response += chunk
            response_placeholder.markdown(full_response)  # Update the response in real-time
        
        # Add assistant response to chat history
        st.session_state.chat_history.append({"role": "assistant", "content": full_response})
