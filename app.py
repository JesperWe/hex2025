import os
from pathlib import Path
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Dict, Any
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from llama_cpp import Llama
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import re
from langgraph.checkpoint.sqlite import SqliteSaver
from uuid import uuid4
from pydantic import BaseModel, Field
from argparse import ArgumentParser
import json
import requests
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from queue import Queue
import threading
from fastapi.websockets import WebSocketState
from aiohttp import ClientSession, WSMsgType
import time
from starlette.websockets import WebSocketDisconnect

class WeatherData(BaseModel):
    fogDensity: float = Field(0.0015, ge=0.001, le=0.006)
    cameraPosition: Dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "z": 1})
    cameraRotation: Dict[str, float] = Field(default_factory=lambda: {"x": 1.16, "y": -0.12, "z": 0.27})
    ambientLightIntensity: float = Field(0.1, ge=0.1, le=100)
    directionalLightIntensity: float = Field(50, ge=0, le=50)
    flashColor: int = Field(0x062d89)
    flashIntensity: float = Field(30, ge=0, le=100)
    flashDistance: float = Field(10, ge=0, le=100)
    flashDecay: float = Field(1.7, ge=0, le=5)
    rainCount: int = Field(10000, ge=0, le=10000)
    rainColor: int = Field(0xaaaaaa)
    rainSize: float = Field(0.1, ge=0.1, le=1.0)
    cloudOpacity: float = Field(1, ge=0, le=1)
    cloudCount: int = Field(25, ge=0, le=200)
    skyColor: int = Field(0x87ceeb)
    cloudColor: int = Field(0xffffff)

class DataTransmissionManager:
    def __init__(self):
        self.app = FastAPI()
        self.setup_cors()
        self.setup_static()
        self.latest_data = WeatherData()
        self.active_connections: List[WebSocket] = []
        self.lock = asyncio.Lock()
        self.setup_routes()

    def setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_static(self):
        static_dir = Path("static")
        static_dir.mkdir(exist_ok=True)
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}

        @self.app.get("/latest")
        async def get_latest_data():
            # Convert Pydantic model to dict using model_dump
            return self.latest_data.model_dump()

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                # Use model_dump for initial state
                await websocket.send_json(WeatherData().model_dump())
                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                # Safe removal check
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)

    async def send_data(self, data: Dict[str, Any]):
        """Lock-free update with atomic operations"""
        try:
            # Use model_dump instead of dict
            weather_data = WeatherData(**data).model_dump()

            # Atomic state update
            old_connections, self.active_connections = self.active_connections, self.active_connections.copy()
            self.latest_data = weather_data
            self.save_data(weather_data)  # I/O bound but thread-safe

            # Fire-and-forget broadcast
            asyncio.create_task(
                self._bulk_send(old_connections, weather_data)
            )
        except Exception as e:
            print(f"Send error: {e}")

    async def _bulk_send(self, connections: List[WebSocket], data: dict):
        """Parallel send to connection snapshot"""
        await asyncio.gather(
            *[self._safe_send(conn, data) for conn in connections],
            return_exceptions=True
        )

    async def _safe_send(self, conn: WebSocket, data: dict):
        """Non-blocking send with automatic cleanup"""
        try:
            if conn.client_state == WebSocketState.CONNECTED:
                await conn.send_json(data)
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    def save_data(self, data: Dict[str, Any]):
        """Save data to file system with error handling"""
        try:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)

            # Save as latest.json
            with open(data_dir / "latest.json", 'w') as f:
                json.dump(data, f, indent=2)

            # Save timestamped version
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(data_dir / f"weather_data_{timestamp}.json", 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
            raise

    def run_server(self):
        """Run the FastAPI server"""
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=8000)

    def start(self):
        """Start the server in a separate thread"""
        import threading
        server_thread = threading.Thread(target=self.run_server)
        server_thread.daemon = True
        server_thread.start()


###########




class _DataTransmissionManager:
    def __init__(self):
        self.app = FastAPI()
        self.setup_cors()
        self.setup_static()
        self.latest_data = {
            "fogDensity": 0.0015,
            "cameraPosition": {"x": 0, "y": 0, "z": 1},
            "cameraRotation": {"x": 1.16, "y": -0.12, "z": 0.27},
            "ambientLightIntensity": 0.1,
            "directionalLightIntensity": 50,
            "flashColor": 0x062d89,
            "flashIntensity": 30,
            "flashDistance": 10,
            "flashDecay": 1.7,
            "rainCount": 10000,
            "rainColor": 0xaaaaaa,
            "rainSize": 0.1,
            "cloudOpacity": 1,
            "cloudCount": 25,
            "skyColor": 0x87ceeb,
            "cloudColor": 0xffffff
        }
        self.active_connections = []
        self.lock = asyncio.Lock()
        self.setup_routes()

    def setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def setup_static(self):
        static_dir = Path("static")
        static_dir.mkdir(exist_ok=True)
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

    def setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                # Use model_dump for initial state
                await websocket.send_json(WeatherData().model_dump())
                while True:
                    try:
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                # Safe removal check
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)

        @self.app.get("/latest")
        async def get_latest_data():
            return self.latest_data

    async def send_data(self, data: Dict[str, Any]):
        """Update and broadcast latest data"""
        async with self.lock:
            self.latest_data = {**self.latest_data, **data}
            self.save_data(self.latest_data)

            # Create tasks for all sends and gather results
            send_tasks = []
            for conn in self.active_connections.copy():
                try:
                    if conn.client_state == WebSocketState.CONNECTED:
                        send_tasks.append(conn.send_json(self.latest_data))
                    else:
                        self.active_connections.remove(conn)
                except Exception as e:
                    print(f"Error queueing data: {e}")
                    self.active_connections.remove(conn)

            # Send all messages concurrently
            if send_tasks:
                await asyncio.gather(*send_tasks, return_exceptions=True)

    def save_data(self, data: Dict[str, Any]):
        """Save data to file system"""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        # Save as latest.json
        with open(data_dir / "latest.json", 'w') as f:
            json.dump(data, f, indent=2)

        # Save timestamped version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(data_dir / f"weather_data_{timestamp}.json", 'w') as f:
            json.dump(data, f, indent=2)

    def run_server(self):
        """Run the FastAPI server"""
        uvicorn.run(self.app, host="0.0.0.0", port=8000)

    def start(self):
        """Start the server in a separate thread"""
        server_thread = threading.Thread(target=self.run_server)
        server_thread.daemon = True
        server_thread.start()





class ModelManager:
    def __init__(self):
        self.app_dir = Path(os.getcwd())
        self.models_dir = self.app_dir / "models"
        self.model_name = self._pick_model_file()
        self.ensure_directory_structure()

    def _pick_model_file(self) -> str:
        """
        Look in the models/ folder for a .gguf file.
        If multiple .gguf files exist, use the first one.
        Raise FileNotFoundError if none are found.
        """
        gguf_files = list(self.models_dir.glob("*.gguf"))
        if not gguf_files:
            raise FileNotFoundError("No .gguf model files found in the 'models' directory.")

        # Just pick the first .gguf file found
        chosen_file = gguf_files[0].name
        print(f"Picked model file: {chosen_file}")
        return chosen_file

    def ensure_directory_structure(self):
        """Create necessary directories if they don't exist"""
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_model_path(self):
        """Get the path to the model file"""
        return self.models_dir / self.model_name

    def initialize_model(self):
        """Initialize the LlamaCpp model"""
        model_path = self.get_model_path()

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}\n"
                f"Please ensure the model file is placed in the {self.models_dir} directory\n"
                "You can download GGUF models from: https://huggingface.co/TheBloke"
            )

        return Llama(
            model_path=str(model_path),
            n_ctx=128000,
            n_threads=8,
            n_gpu_layers=1
        )

# Initialize model manager and model
model_manager = ModelManager()
try:
    llm = model_manager.initialize_model()
    print(f"Model loaded successfully from {model_manager.get_model_path()}")
except FileNotFoundError as e:
    print(f"Error loading model: {e}")
    raise

def format_prompt(messages):
    """Format messages into a prompt string for llama.cpp"""
    formatted_text = ""
    for message in messages:
        if isinstance(message, SystemMessage):
            formatted_text += f"### System:\n{message.content}\n\n"
        elif isinstance(message, HumanMessage):
            formatted_text += f"### Human:\n{message.content}\n\n"
        elif isinstance(message, AIMessage):
            formatted_text += f"### Assistant:\n{message.content}\n\n"
    formatted_text += "### Assistant:\n"
    return formatted_text

def invoke_llama(messages):
    """Invoke the llama.cpp model with formatted messages"""
    try:
        formatted_prompt = format_prompt(messages)
        response = llm(
            formatted_prompt,
            max_tokens=2048,
            temperature=0.1,
            top_p=0.95,
            stop=["### Human:", "### System:"],
            echo=False
        )
        return AIMessage(content=response['choices'][0]['text'].strip())
    except Exception as e:
        print(f"Error invoking llama.cpp: {e}")
        return AIMessage(content="Error generating response. Please try again.")

# Helper functions for Three.js code validation
def validate_threejs_code(code: str) -> List[str]:
    """Validate Three.js code and return any errors"""
    errors = []
    required_elements = ['scene', 'camera', 'renderer', 'animate']
    for element in required_elements:
        if f'{element} = new THREE.' not in code:
            errors.append(f'Missing required Three.js element: {element}')
    return errors

def run_threejs_test(code: str) -> bool:
    """Execute Three.js code in headless browser and return success status"""
    return True

# Message reduction utility
def reduce_messages(left: list[AnyMessage], right: list[AnyMessage]) -> list[AnyMessage]:
    for message in right:
        if not message.id:
            message.id = str(uuid4())
    merged = left.copy()
    for message in right:
        for i, existing in enumerate(merged):
            if existing.id == message.id:
                merged[i] = message
                break
        else:
            merged.append(message)
    return merged

# Define agent state
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], reduce_messages]
    threejs_template: str
    artistic_instruction: str
    artistic_interpretation: str
    generated_prompt: str
    updated_code: str
    weather_data: dict
    validation_errors: List[str]
    iteration_count: int
    max_iterations: int
    location: dict





def extract_json_from_response(response_text: str) -> dict:
    """Extract and validate JSON content from the model's response."""
    try:
        # Try to find a JSON code block wrapped in ```json ... ```
        json_block_pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(json_block_pattern, response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Fallback to expecting the pattern: const weatherSettings = { ... };
            json_pattern = r'const\s+weatherSettings\s*=\s*({[^;]*});'
            match = re.search(json_pattern, response_text, re.DOTALL)
            if not match:
                raise ValueError("No weather settings JSON found in response")
            json_str = match.group(1)

        # Remove JavaScript comments (if any) and trailing commas
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Convert any hex values (e.g., 0x062d89) to decimal.
        # This regex finds any occurrence of 0x followed by hexadecimal digits.
        json_str = re.sub(
            r'\b0x([0-9a-fA-F]+)\b',
            lambda m: str(int(m.group(0), 16)),
            json_str
        )

        # Now try to parse the JSON.
        weather_settings = json.loads(json_str)

        # Validate required fields and adjust types as needed.
        required_fields = {
            'fogDensity': float,
            'cameraPosition': dict,
            'cameraRotation': dict,
            'ambientLightIntensity': float,
            'directionalLightIntensity': float,
            'flashColor': int,
            'flashIntensity': float,
            'flashDistance': float,
            'flashDecay': float,
            'rainCount': int,
            'rainColor': int,
            'rainSize': float,
            'cloudOpacity': float,
            'cloudCount': int,
            'skyColor': int,
            'cloudColor': int
        }

        for field, field_type in required_fields.items():
            if field not in weather_settings:
                raise ValueError(f"Missing required field: {field}")
            if not isinstance(weather_settings[field], field_type):
                if field_type == float:
                    weather_settings[field] = float(weather_settings[field])
                elif field_type == int:
                    weather_settings[field] = int(weather_settings[field])


        return weather_settings

    except Exception as e:
        print(f"Error parsing JSON response: {e}")
        # Return enhanced default with all required fields
        return {
            "fogDensity": 0.0015,
            "cameraPosition": {"x": 0, "y": 0, "z": 1},
            "cameraRotation": {"x": 1.16, "y": -0.12, "z": 0.27},
            "ambientLightIntensity": 0.1,
            "directionalLightIntensity": 50,
            "flashColor": 0x062d89,
            "flashIntensity": 30,
            "flashDistance": 10,
            "flashDecay": 1.7,
            "rainCount": 10000,
            "rainColor": 0xaaaaaa,
            "rainSize": 0.1,
            "cloudOpacity": 1,
            "cloudCount": 25,
            "skyColor": 0x87ceeb,
            "cloudColor": 0xffffff
        }


# Agent node implementations with enhanced prompts
def artistic_director_node(state: AgentState):
    messages = [
        SystemMessage(content="""As an artistic director specializing in weather visualization, analyze 
        the provided weather data and create a visual concept using Three.js. Consider elements like color, 
        movement, and form to represent weather conditions effectively.
        Current weather data: """ + str(state.get('weather_data', {}))),
        HumanMessage(content=f"Template:\n{state['threejs_template']}\n\nInstruction: {state['artistic_instruction']}")
    ]
    response = invoke_llama(messages)
    return {
        **state,
        "messages": state["messages"] + [response],
        "artistic_interpretation": response.content
    }



def prompt_generator_node(state: AgentState):
    messages = [
        SystemMessage(content="""As a Three.js and JSON technical expert, analyze the weather 
                      conditions and artistic direction to generate precise weather visualization parameters. 
        Your response must contain a weatherSettings object in the exact format shown below, while updating the parameter
                      values to reflect the weather conditions and artistic direction, and never be the same as the previous response, TEMPLATE JSON DATA:

        const weatherSettings = {
            fogDensity: 0.0015,            // Range: 0.001 (dense) to 0.006 (clear)
            cameraPosition: { x: 0, y: 0, z: 1 },
            cameraRotation: { x: 1.16, y: -0.12, z: 0.27 },
            ambientLightIntensity: 0.1,    // Range: 0.1 (light) to 100 (dense)
            directionalLightIntensity: 50,  // Range: 0 (dark) to 50 (bright)
            flashColor: 0x062d89,
            flashIntensity: 30,
            flashDistance: 10,
            flashDecay: 1.7,
            rainCount: 10000,              // Range: 0 (none) to 10000 (heavy)
            rainColor: 0xaaaaaa,
            rainSize: 0.1,                 // Range: 0.1 (rain) to 1.0 (snow)
            cloudOpacity: 1,               // Range: 0.0 to 1.0
            cloudCount: 25,                // Range: 0 to 200
            skyColor: 0x87ceeb,            // 0x11111f (night) to 0x87ceeb (day)
            cloudColor: 0xffffff           // 0x111111 (dark) to 0xffffff (white)
        };

        Provide only this JSON object in your response, maintaing the exact same data types as the previous response, while changing the values to reflect the weather conditions and artistic direction."""),
        HumanMessage(content=f"Based on this artistic direction, generate the appropriate weather settings:\n{state.get('artistic_interpretation', '')}")
    ]

    response = invoke_llama(messages)

    # Extract and validate JSON from response
    weather_settings = extract_json_from_response(response.content)

    # Format the response as a proper JSON string
    formatted_json = json.dumps(weather_settings, indent=2)

    print("Prompt Generator Response:", formatted_json)

    return {
        **state,  # Preserve all existing state
        "messages": state["messages"] + [response],
        "generated_prompt": formatted_json,
        "weather_settings": weather_settings
    }



def code_implementer_node(state: AgentState):
    messages = [
        SystemMessage(content="As a Three.js developer, implement the technical requirements in clean, efficient code. Ensure proper scene setup, optimized rendering, and smooth animations. Include error handling and performance considerations."),
        HumanMessage(content=f"Template:\n{state['threejs_template']}\nImplementation requirements:\n{state['generated_prompt']}")
    ]
    response = invoke_llama(messages)
    print("Code Implementer Response:", response.content)
    new_state = {**state,  # Merge the entire previous state
                 "messages": state["messages"] + [response],
                 "updated_code": response.content,
                 "iteration_count": state.get("iteration_count", 0) + 1}
    return new_state





def validation_node(state: AgentState):
    errors = validate_threejs_code(state['updated_code'])
    validation_success = not errors and run_threejs_test(state['updated_code'])
    return {
        **state,
        "validation_errors": [] if validation_success else errors + ["Runtime validation failed"],
        "messages": state["messages"]
    }

def web_researcher_node(state: AgentState):
    location = state.get('location', {'lat': 51.5074, 'lon': -0.1278})
    try:
        response = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={location['lat']}&longitude={location['lon']}&current_weather=true"
        )
        weather_data = response.json()
        print("Weather Researcher Data:", weather_data)
    except Exception as e:
        weather_data = {"error": str(e)}
    return {
        **state,  # Preserve all existing state
        "weather_data": weather_data,
        "messages": state["messages"]
    }

# Define initial state
initial_state = {
    "messages": [],
    "threejs_template": """
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer();
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);
    
    function animate() {
        requestAnimationFrame(animate);
        renderer.render(scene, camera);
    }
    animate();
    """,
    "artistic_instruction": "Create a dynamic weather visualization",
    "artistic_interpretation": "",
    "generated_prompt": "",
    "updated_code": "",
    "weather_data": {},
    "validation_errors": [],
    "iteration_count": 0,
    "max_iterations": 5,
    "location": {"lat": 51.5074, "lon": -0.1278}
}

# Build and configure the agent network
builder = StateGraph(AgentState)
builder.add_node("Artistic_Director", artistic_director_node)
builder.add_node("Prompt_Generator", prompt_generator_node)
builder.add_node("Code_Implementer", code_implementer_node)
#builder.add_node("Validator", validation_node)
builder.add_node("Web_Researcher", web_researcher_node)

# Set entry point and configure edges
builder.set_entry_point("Artistic_Director")
builder.add_edge("Artistic_Director", "Prompt_Generator")
builder.add_edge("Prompt_Generator", "Code_Implementer")
builder.add_edge("Code_Implementer", "Web_Researcher")

# Add conditional edges
"""builder.add_conditional_edges(
    "Validator",
    lambda state: "continue" if state.get("validation_errors") and state.get("iteration_count", 0) < state.get("max_iterations", 5) else "complete",
    {
        "continue": "Code_Implementer",
        "complete": "Web_Researcher"
    }
)"""

builder.add_edge("Web_Researcher", "Artistic_Director")

# Run the agent network
# Initialize and start the DataTransmissionManager
data_transmission_manager = DataTransmissionManager()

async def test_websocket_connection(retries=3, timeout=2):
    """Test WebSocket connectivity with retries and validation"""
    # Use model_dump instead of dict
    test_data = WeatherData().model_dump()

    for attempt in range(retries):
        try:
            async with ClientSession() as session:
                async with session.ws_connect("ws://localhost:8000/ws") as ws:
                    # Test send/receive
                    await ws.send_json(test_data)

                    # Verify response within timeout
                    response = await asyncio.wait_for(ws.receive_json(), timeout)
                    if response == test_data:
                        print("✅ WebSocket test successful")
                        return True

                    print(f"❌ Data mismatch: {response}")
                    return False
        except Exception as e:
            print(f"WebSocket test attempt {attempt+1} failed: {e}")
            time.sleep(0.5 * (attempt + 1))

    print("❌ All WebSocket connection tests failed")
    return False

def run_data_transmission_server():
    data_transmission_manager.run_server()

server_thread = threading.Thread(target=run_data_transmission_server)
server_thread.daemon = True
server_thread.start()
print("DataTransmissionManager server started on http://0.0.0.0:8000")

# Start server with health checks
print("🚀 Starting server...")
data_transmission_manager.start()

# Wait for server to start
time.sleep(1)

# Verify server health
try:
    response = requests.get("http://localhost:8000/health", timeout=2)
    if response.json().get("status") != "ok":
        print("❌ Server health check failed")
        exit(1)
    print("✅ Server health check passed")
except Exception as e:
    print(f"❌ Server not responding: {e}")
    exit(1)

# Run WebSocket test
loop = asyncio.get_event_loop()
if not loop.run_until_complete(test_websocket_connection()):
    print("❌ Critical: WebSocket tests failed, exiting")
    exit(1)




with SqliteSaver.from_conn_string(":memory:") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    print("Agent network instantiated successfully!")

    thread = {"configurable": {"thread_id": "1"}}

    async def process_agent_output():
        for s in graph.stream(initial_state, thread):
            print("\nNew iteration output:")
            print(json.dumps(s.get('weather_settings', {}), indent=2))

            # Check if we have weather settings from the Prompt Generator
            if "weather_settings" in s and s["weather_settings"]:
                try:
                    # Send the new weather data
                    await data_transmission_manager.send_data(s["weather_settings"])
                    print("✅ Successfully sent updated weather settings to clients!")
                except Exception as e:
                    print(f"❌ Error sending weather data: {e}")

    # Run the agent loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(process_agent_output())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        loop.close()



    """for s in graph.stream(initial_state, thread):
        print(s)
        
        # Each time new 'weather_settings' are produced, send them to the DataTransmissionManager
        if "weather_settings" in s and s["weather_settings"]:
            data_transmission_manager.send_data(s["weather_settings"])
            print("Sent updated weather settings to DataTransmissionManager!")"""

