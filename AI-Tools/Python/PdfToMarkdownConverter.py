from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
import asyncio
from langchain_groq import ChatGroq

# Initialize Groq model with empty API key (replace with your key if available)
model = ChatGroq(model="openai/gpt-oss-120b", api_key="")

# Configure MCP server parameters for STDIO mode
#install  markitdown-mcp server 
#and RUN Command ```  markitdown-mcp ```
server_params = StdioServerParameters(
   command="markitdown-mcp",
   args=[]  # No additional arguments needed for STDIO mode
)

async def run_conversion(pdf_path: str):
   async with stdio_client(server_params) as (read, write):
       async with ClientSession(read, write) as session:
           await session.initialize()
           print("MCP Session Initialized.")

           # Load available MCP tools
           tools = await load_mcp_tools(session)
           print(f"Loaded Tools: {[tool.name for tool in tools]}")

           # Create ReAct agent with model and tools
           agent = create_react_agent(model, tools)
           print("ReAct Agent Created.")

           # Prepare file URI (convert local path to file:// URI)
           file_uri = f"{pdf_path}"

           # Invoke agent with conversion request
           response = await agent.ainvoke({
               "messages": [("user", f"Convert {file_uri} to markdown using Markitdown MCP just return the output from MCP server")]
           })

           # Return the last message content
           return response["messages"][-1].content

if __name__ == "__main__":
   # Use absolute path to your PDF file
   #before adding your pdf to path please Run a PDF server like http-server or python -m http.server
   #for example : py -m http.server 8080
   pdf_path = "path_to_your_pdf_file.pdf"

   # Run the asynchronous conversion
   result = asyncio.run(run_conversion(pdf_path))

   # Save the markdown output to a file
   with open("pdf.md", 'w', encoding='utf-8') as f:
       f.write(result)

   print("\nMarkdown Conversion Result:")
   print(result)
