from flask import Flask, render_template, request, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import json
import re
from together import Together

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize the Together client
client = Together(api_key="874bde375c479480654683abd21050ae0381971860908bc4dd368b282b3fa94b")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_response', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def get_response():
    try:
        # Extract the prompt and chat history from the request
        if request.method == 'POST':
            prompt = request.form.get('prompt')
            chat_history = json.loads(request.form.get('chat_history', '[]'))
        else:  # GET request
            prompt = request.args.get('prompt')
            chat_history = json.loads(request.args.get('chat_history', '[]'))

        if not prompt:
            return jsonify({'error': 'Empty prompt'}), 400

        # Add the user's message to the chat history
        chat_history.append({"role": "user", "content": prompt})

        # Call the Together API to stream the response
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",
            messages=chat_history,
            max_tokens=500,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=[""],
            stream=True
        )

        def generate(response):
            try:
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
                                            yield f"data: {json.dumps({'response': buffer[:think_start]})}\n\n"
                                        buffer = buffer[think_start:]
                                        in_think_block = True
                                    else:
                                        # No think tag found, send the buffer
                                        yield f"data: {json.dumps({'response': buffer})}\n\n"
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
                    yield f"data: {json.dumps({'response': buffer})}\n\n"
                
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                print(f"Error during streaming: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(response), content_type='text/event-stream')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    main()
