from flask import Flask, render_template, request, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import json
import pandas as pd
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

# Configure research database path
RESEARCH_DB_PATH = r'C:\Users\IOTTC-05\Documents\deepseekrev\RESEARCH PRODUCTIVITY TEMPLATE.xlsx'

def load_research_db():
    """Load the research database with error handling"""
    try:
        df = pd.read_excel(RESEARCH_DB_PATH)
        print("Research database loaded successfully")
        print(f"Columns in the database: {df.columns.tolist()}")  # Debug: Print columns
        return df
    except Exception as e:
        print(f"Error loading research database: {e}")
        return None

def refresh_research_db():
    """Refresh the research database"""
    global research_db
    research_db = load_research_db()

# Initial database load
research_db = load_research_db()

def is_research_topic(prompt):
    """
    Check if the prompt is related to research topics.
    Returns True if research-related keywords are found.
    """
    research_keywords = {
        'research', 'study', 'paper', 'article', 'publication', 
        'thesis', 'dissertation', 'findings', 'methodology',
        'analysis', 'results', 'conclusion', 'experiment'
    }
    prompt_words = set(prompt.lower().split())
    return bool(prompt_words & research_keywords)

def query_research_db(prompt):
    """
    Query the research database based on the prompt.
    Returns a list of matching research entries.
    """
    if research_db is None:
        print("Research database not available")
        return []
        
    try:
        # Split prompt into keywords
        keywords = [word for word in prompt.lower().split() if len(word) > 2]
        
        if not keywords:
            return []
            
        # Create search pattern
        search_pattern = '|'.join(keywords)
        
        # Search across multiple columns with error handling
        results = research_db[
            research_db['Title of the Study'].str.contains(search_pattern, case=False, na=False, regex=True) |
            research_db['Name of Faculty'].str.contains(search_pattern, case=False, na=False, regex=True) |
            research_db['Year'].astype(str).str.contains(search_pattern, case=False, na=False, regex=True) |
            research_db['Presented In'].str.contains(search_pattern, case=False, na=False, regex=True) |
            research_db['Published In'].str.contains(search_pattern, case=False, na=False, regex=True)
        ]
        
        # Sort by relevance (you can modify this based on your needs)
        results = results.head(3)  # Limit to top 3 most relevant results
        
        print(f"Found {len(results)} matching research entries")  # Debug: Print number of results
        return results.to_dict(orient='records')
    except Exception as e:
        print(f"Error querying database: {e}")
        return []

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

        # Check if the prompt is related to research topics
        if is_research_topic(prompt):
            print("Prompt is research-related. Querying database...")  # Debug: Log research topic detection
            # Query the research database
            research_results = query_research_db(prompt)
            if research_results:
                print("Research results found. Augmenting prompt...")  # Debug: Log results found
                # Create a system message with the research context
                research_context = "Based on our research database, here are relevant findings:\n\n"
                for idx, result in enumerate(research_results, 1):
                    research_context += f"Research {idx}:\n"
                    research_context += f"Title of the Study: {result.get('Title of the Study', 'N/A')}\n"
                    research_context += f"Name of Faculty: {result.get('Name of Faculty', 'N/A')}\n"
                    research_context += f"Year: {result.get('Year', 'N/A')}\n"
                    research_context += f"Presented In: {result.get('Presented In', 'N/A')}\n"
                    research_context += f"Published In: {result.get('Published In', 'N/A')}\n\n"
                
                # Add research context as a system message
                chat_history.append({
                    "role": "system",
                    "content": research_context
                })
            else:
                print("No research results found for the prompt.")  # Debug: Log no results
        else:
            print("Prompt is not research-related.")  # Debug: Log non-research topic

        # Call the Together API with the complete chat history
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
        print(f"Error in get_response: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/refresh-db', methods=['POST'])
@limiter.limit("1 per minute")
def refresh_database():
    """Endpoint to manually refresh the research database"""
    try:
        refresh_research_db()
        return jsonify({'message': 'Database refreshed successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)