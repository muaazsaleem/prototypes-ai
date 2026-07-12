import os
import sys
import importlib.util
import textwrap
import inspect
from datetime import datetime
from google import genai
from google.genai import types

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Initialize the rich console
console = Console()

SYSTEM_INSTRUCTION = """
You are a highly capable Self-Evolving AI Agent. Your primary objective is to solve the user's request.
You have access to a small set of pre-defined tools.
If you realize you need a tool that you do not currently have (such as executing shell commands, doing file system operations, compiling code, etc.), you have a special meta-tool called `create_and_register_new_tool`.

Guidelines for creating new tools:
1. Before creating a tool, design it conceptually. Ensure it is focused, simple, and safe.
2. The Python code you provide must define a single, standard, self-contained Python function with the exact name you specified.
3. The function MUST include:
   - Proper Python type annotations/hints for all its arguments and return types.
   - A complete docstring describing what the tool does, its arguments, and its return value. The SDK uses these type hints and docstring to automatically generate the JSON schema.
   - Any necessary imports inside the function itself or at the top of the code.
4. An excellent example of a tool you should write when you need terminal or shell execution capability is a bash command executor tool named `run_bash_command` which takes a `command` string and returns the command's stdout and stderr.
5. Once a tool is created and registered successfully, you will receive a success response. In your very next turn, the new tool will be available to you as an active tool, and you can call it immediately!
6. If a tool you created raises an error or fails, don't worry! Analyze the error, rewrite the tool using `create_and_register_new_tool` to patch/fix it, and try again.

Be autonomous, professional, and clear in your reasoning.
"""

class SelfEvolvingAgent:
    def __init__(self):
        # Initialize the official Google Gen AI Client
        # Automatically picks up GEMINI_API_KEY from environment
        self.client = genai.Client()
        self.model_id = "gemini-2.5-flash"
        
        # We start with some pre-defined tools
        self.active_tools = {
            "get_current_time": self.get_current_time,
            "fetch_webpage_content": self.fetch_webpage_content,
            "create_and_register_new_tool": self.create_and_register_new_tool
        }
        
        # Conversation history stored as types.Content objects
        self.history = []
        
        # Ensure the tools folder exists and has an __init__.py
        os.makedirs("tools", exist_ok=True)
        init_file = os.path.join("tools", "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Dynamic tools directory\n")
                
    def get_current_time(self) -> str:
        """
        Returns the current system date and time.
        
        Returns:
            str: The current system date and time as a string.
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def fetch_webpage_content(self, url: str) -> str:
        """
        Simulates or executes fetching the text content of a webpage.
        
        Args:
            url: The URL of the webpage to fetch.
            
        Returns:
            str: The contents of the webpage (truncated to avoid exceeding context limits).
        """
        import requests
        try:
            headers = {"User-Agent": "SelfEvolvingAgent/1.0"}
            response = requests.get(url, headers=headers, timeout=5)
            return response.text[:1000]
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"
            
    def create_and_register_new_tool(self, name: str, code: str, description: str) -> str:
        """
        Creates and registers a new tool for the agent by writing its Python implementation, 
        dynamically loading it into the environment, and making it available in the agent's toolset.
        
        Args:
            name: The name of the function to create. Must be a valid Python identifier.
            code: The complete Python code defining the function. The function MUST:
                  - Use the exact name specified in the 'name' parameter.
                  - Include all necessary imports inside the function or at the module level.
                  - Include proper Python type hints for all parameters and return types.
                  - Include a comprehensive docstring describing its behavior, arguments, and return.
            description: A short, clear explanation of what this tool does.
        """
        console.print(f"\n[bold magenta]🛠️  Meta-tool Invoked: Creating and Registering '{name}'...[/bold magenta]")
        
        # Validation
        if not name.isidentifier():
            return f"Error: '{name}' is not a valid Python identifier."
            
        file_path = os.path.join("tools", f"{name}.py")
        
        try:
            # Save code to the dynamic tools folder
            with open(file_path, "w") as f:
                f.write(code)
                
            console.print(f"  [dim]Saved Python source file to {file_path}[/dim]")
            
            # Dynamically import and execute the module
            spec = importlib.util.spec_from_file_location(name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for module {name} at {file_path}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"tools.{name}"] = module
            spec.loader.exec_module(module)
            
            # Extract the actual function reference
            if not hasattr(module, name):
                raise AttributeError(f"Module does not contain a function named '{name}'")
                
            func = getattr(module, name)
            if not callable(func):
                raise TypeError(f"'{name}' extracted from module is not callable")
                
            # Add to the agent's active tools dictionary
            self.active_tools[name] = func
            console.print(f"  [bold green]✓ Tool '{name}' has been dynamically loaded and registered![/bold green]")
            
            # Verify its inspectable signature
            sig = inspect.signature(func)
            console.print(f"  [dim]Signature: {name}{sig}[/dim]")
            
            return (
                f"Success: Dynamic tool '{name}' has been successfully written, loaded, and registered. "
                f"You can now call '{name}' in your next turn with correct arguments!"
            )
            
        except Exception as e:
            console.print(f"  [bold red]✗ Failed to register tool '{name}': {str(e)}[/bold red]")
            # Attempt to clean up the file
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return f"Failure: Could not create and register tool '{name}'. Error: {str(e)}"

    def print_history_block(self):
        """Displays the conversation history formatted with Rich panels according to terminal-output-style."""
        input_elements = []
        for index, item in enumerate(self.history):
            role = item.role
            # Format parts of the message
            content_parts = []
            for part in item.parts:
                if part.text:
                    content_parts.append(part.text)
                elif part.function_call:
                    content_parts.append(f"Function Call -> {part.function_call.name}({part.function_call.args})")
                elif part.function_response:
                    content_parts.append(f"Function Response [{part.function_response.name}] -> {part.function_response.response}")
            
            content = "\n".join(content_parts)
            
            if role == "system":
                label_style = "dim"
                content_style = "dim"
                role_label = "SYSTEM"
            elif role == "user":
                label_style = "bold blue"
                content_style = "blue"
                role_label = "USER"
            elif role in ("model", "assistant"):
                label_style = "bold green"
                content_style = "green"
                role_label = "ASSISTANT"
            elif role == "tool":
                label_style = "bold yellow"
                content_style = "yellow"
                role_label = "TOOL"
            else:
                label_style = "white"
                content_style = "white"
                role_label = role.upper()
                
            indent = " " * (len(role_label) + 2)
            wrapped = textwrap.fill(content, width=82, subsequent_indent=indent)
            
            input_elements.append(Text.assemble((f"{role_label}: ", label_style), (wrapped, content_style)))
            input_elements.append(Rule(style="bright_black"))

        if input_elements:
            input_elements.pop() # Remove trailing rule

        console.print(
            Panel(
                Group(*input_elements),
                title="[bold bright_black]Model Input[/bold bright_black]",
                border_style="bright_black",
                padding=(1, 2),
            )
        )
        console.print()

    def run_task(self, prompt: str) -> str:
        """
        Runs the agent on the given prompt.
        Handles the manual tool call / execution loop and dynamic tool updates.
        """
        console.print(Rule("[bold]Agent Task Started[/bold]", style="white"))
        console.print() # Blank line after Rule
        console.print(f"[bold blue]> USER REQUEST:[/bold blue]\n  [blue]{prompt}[/blue]\n")
        
        # Add the user query to conversation history
        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
        
        step = 1
        while True:
            console.print(Rule(f"[bold]Step {step}[/bold]", style="white"))
            console.print() # Blank line after Rule
            
            # Print history block for full transparency
            self.print_history_block()
            
            # List current registered tools
            registered_tool_names = list(self.active_tools.keys())
            console.print(f"[dim]Available Tools to Gemini: {', '.join(registered_tool_names)}[/dim]\n")
            
            # Send the request to Gemini
            # We must pass system_instruction and tools dynamically
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=list(self.active_tools.values()),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.1 # Low temperature for reliable function calling/logic
            )
            
            with console.status("[bold cyan]Thinking & Planning...[/bold cyan]"):
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=self.history,
                    config=config
                )
            
            # Check if there are candidate responses
            if not response.candidates:
                console.print("[bold red]Error: No candidates returned from Gemini.[/bold red]")
                break
                
            model_content = response.candidates[0].content
            
            # Save model's response to history
            self.history.append(model_content)
            
            # Handle text responses (if any) and print them
            for part in model_content.parts:
                if part.text:
                    wrapped_response = textwrap.fill(part.text, width=82, subsequent_indent="             ")
                    response_content = Text.assemble(
                        ("ASSISTANT: ", "bold green"),
                        (wrapped_response, "italic")
                    )
                    console.print(
                        Panel(
                            response_content,
                            title="[bold bright_black]Model Response[/bold bright_black]",
                            border_style="bright_black",
                            padding=(1, 2),
                            highlight=False,
                        )
                    )
                    console.print()
            
            # Check if the model requested any function calls
            function_calls = response.function_calls
            if not function_calls:
                console.print("[bold green]✓ Task Completed successfully! No more tool calls required.[/bold green]")
                # Return the last printed text
                final_text = "".join([part.text for part in model_content.parts if part.text])
                return final_text
                
            # Execute requested function calls
            tool_parts = []
            for fc in function_calls:
                console.print(f"\n[bold yellow]📞  Model Requested Tool Call:[/bold yellow] [bold cyan]{fc.name}[/bold cyan] with args [bold magenta]{fc.args}[/bold magenta]")
                
                # Check if the tool exists
                if fc.name in self.active_tools:
                    tool_func = self.active_tools[fc.name]
                    try:
                        # Execute tool
                        result = tool_func(**fc.args)
                        console.print(f"  [bold green]✓ Success:[/bold green] Tool returned type [green]{type(result).__name__}[/green]")
                    except Exception as e:
                        result = f"Error during tool execution: {str(e)}"
                        console.print(f"  [bold red]✗ Error executing tool:[/bold red] {str(e)}")
                else:
                    result = f"Error: Tool '{fc.name}' does not exist."
                    console.print(f"  [bold red]✗ Error:[/bold red] Tool '{fc.name}' not registered.")
                
                # Format the response back to Gemini
                res_part = types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result}
                )
                tool_parts.append(res_part)
                
            # Save tool execution results to history
            self.history.append(types.Content(role="tool", parts=tool_parts))
            
            step += 1
            console.print()
