from langchain_groq import ChatGroq
# Note: AgentExecutor is not used by the new custom loop directly but create_react_agent might need it or its components.
# For now, keeping it to see if create_react_agent is self-sufficient.
# from langchain.agents import AgentExecutor
from langchain.agents import create_react_agent # Corrected import path if different from AgentExecutor's module
from langchain_core.prompts import ChatPromptTemplate # MessagesPlaceholder not used in current prompt
from langchain_core.messages import HumanMessage, AIMessage

from smartdoc_agent.core.tools import (
    analyze_document_structure,
    create_formatting_plan,
    apply_contextual_formatting,
    validate_formatting_result
)
from smartdoc_agent.config import get_groq_api_key

# Required for new run loop
import json
import ast
import traceback # Import traceback
import time # For timing LLM calls
from langchain_core.agents import AgentAction, AgentFinish


class DocumentFormattingAgent:
    def __init__(self, model_name="llama3-70b-8192", temperature=0):
        self.api_key = get_groq_api_key()
        if not self.api_key or self.api_key in ["YOUR_GROQ_API_KEY_HERE"] or "DUMMY" in self.api_key.upper() :
            print(f"⚠️ DocumentFormattingAgent __init__: API key is dummy, placeholder, or missing ('{self.api_key}'). Agent's LLM may fail.")

        self.llm = ChatGroq(
            groq_api_key=self.api_key,
            model_name=model_name,
            temperature=temperature
        )

        self.tools = [
            analyze_document_structure,
            create_formatting_plan,
            apply_contextual_formatting,
            validate_formatting_result
        ]
        self.tool_names = [tool.name for tool in self.tools]

        prompt_template = """
        You are an expert document formatting assistant. Your goal is to help users format their .docx documents.
        You have access to the following tools:

        {tools}

        To use a tool, use the following format:
        Thought: Do I need to use a tool? Yes
        Action: The action to take. Must be one of [{tool_names}]
        Action Input: If the tool takes multiple arguments, provide a VALID JSON string representing a dictionary of these arguments (e.g., "{{\"arg1\": \"value1\", \"arg2\": \"value2\"}}"). Ensure keys and string values are in double quotes. If the tool takes a single simple string argument (like a file path for 'analyze_document_structure'), provide just that string WITHOUT surrounding quotes unless they are part of the path itself.
        Observation: The result of the action.

        When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:
        Thought: Do I need to use a tool? No
        Final Answer: [your response here]

        A few important rules:
        1. When a tool provides output (Observation), and you need to use that output as input for a subsequent tool, you MUST use the exact, complete output from the Observation for the relevant parameter, UNLESS a special placeholder is specified below.
        2. Ensure your Action Input is correctly formatted for the tool.
        3. For the 'create_formatting_plan' tool:
           - Its 'document_analysis_json' parameter requires a JSON string.
           - Look at the Observation from the 'analyze_document_structure' tool. This observation is a large JSON string.
           - From this large JSON string, find the 'document_path' string value and the 'summary' object.
           - Create a NEW, smaller JSON string that looks like this: {{"document_path": "<actual_path_here>", "summary": <actual_summary_object_here>}}
           - Use this NEW, smaller JSON string as the value for the 'document_analysis_json' parameter in the Action Input for 'create_formatting_plan'.
           Example:
           Observation: {{"elements": [...], "document_path": "path/doc.docx", "summary": {{"total_elements": 10, "paragraph_count": 5, "heading_count": 2}}, ...other_keys...}}
           Thought: I need to make a plan. I will extract the document_path and summary from the observation and use that for create_formatting_plan.
           Action: create_formatting_plan
           Action Input: {{"document_analysis_json": "{{\"document_path\": \"path/doc.docx\", \"summary\": {{\"total_elements\": 10, \"paragraph_count\": 5, \"heading_count\": 2}}}}", "user_goal": "the user's original goal text"}}
        4. For the 'apply_contextual_formatting' tool:
           - It needs 'doc_path', 'formatting_plan_json', 'document_analysis_json', and 'output_doc_path'.
           - 'doc_path' is the original input document path.
           - For 'formatting_plan_json', you MUST use the literal string placeholder: "$CURRENT_FORMATTING_PLAN".
           - For 'document_analysis_json', you MUST use the literal string placeholder: "$FULL_ORIGINAL_ANALYSIS".
           - 'output_doc_path' is where the formatted document should be saved.
           Example Action Input: {{"doc_path": "doc.docx", "formatting_plan_json": "$CURRENT_FORMATTING_PLAN", "document_analysis_json": "$FULL_ORIGINAL_ANALYSIS", "output_doc_path": "doc_formatted.docx"}}
        5. For the 'validate_formatting_result' tool:
           - It requires these arguments: 'original_doc_analysis_json', 'modified_doc_analysis_json', 'formatting_plan_json', and 'user_goal'.
           - For 'original_doc_analysis_json', you MUST use the literal string placeholder: "$FULL_ORIGINAL_ANALYSIS".
           - For 'modified_doc_analysis_json', you MUST use the literal string placeholder: "$FULL_MODIFIED_ANALYSIS" (this refers to the analysis of the document *after* formatting has been applied by `apply_contextual_formatting` and the modified document re-analyzed by `analyze_document_structure`).
           - For 'formatting_plan_json', you MUST use the literal string placeholder: "$CURRENT_FORMATTING_PLAN".
           - 'user_goal' is the original user goal text provided at the start of the task.
           Example Action Input for 'validate_formatting_result':
           {{"original_doc_analysis_json": "$FULL_ORIGINAL_ANALYSIS", "modified_doc_analysis_json": "$FULL_MODIFIED_ANALYSIS", "formatting_plan_json": "$CURRENT_FORMATTING_PLAN", "user_goal": "The user's original request text here"}}

        Begin!

        Previous conversation history:
        {chat_history}

        New input: {input}
        {agent_scratchpad}
        """

        self.prompt = ChatPromptTemplate.from_template(prompt_template).partial(
            tools="\n".join([f"{tool.name}: {tool.description}" for tool in self.tools]),
            tool_names=", ".join([tool.name for tool in self.tools]),
        )

        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        self.chat_history = []
        self.full_original_analysis_json = None
        self.current_formatting_plan_json = None
        self.full_modified_analysis_json = None
        self.current_doc_path = None
        self.current_output_doc_path = None
        self.PLACEHOLDER_ORIGINAL_ANALYSIS = "$FULL_ORIGINAL_ANALYSIS"
        self.PLACEHOLDER_MODIFIED_ANALYSIS = "$FULL_MODIFIED_ANALYSIS"
        self.PLACEHOLDER_FORMATTING_PLAN = "$CURRENT_FORMATTING_PLAN"

    def _substitute_placeholders(self, action_input: dict) -> dict:
        processed_input = {}
        for key, value in action_input.items():
            if value == self.PLACEHOLDER_ORIGINAL_ANALYSIS:
                if self.full_original_analysis_json:
                    processed_input[key] = self.full_original_analysis_json
                    print(f"Substituted {self.PLACEHOLDER_ORIGINAL_ANALYSIS} for key '{key}'")
                else:
                    raise ValueError(f"Agent tried to use placeholder {self.PLACEHOLDER_ORIGINAL_ANALYSIS} but no original analysis is stored.")
            elif value == self.PLACEHOLDER_MODIFIED_ANALYSIS:
                if self.full_modified_analysis_json:
                    processed_input[key] = self.full_modified_analysis_json
                    print(f"Substituted {self.PLACEHOLDER_MODIFIED_ANALYSIS} for key '{key}'")
                else:
                    raise ValueError(f"Agent tried to use placeholder {self.PLACEHOLDER_MODIFIED_ANALYSIS} but no modified analysis is stored.")
            elif value == self.PLACEHOLDER_FORMATTING_PLAN:
                if self.current_formatting_plan_json:
                    processed_input[key] = self.current_formatting_plan_json
                    print(f"Substituted {self.PLACEHOLDER_FORMATTING_PLAN} for key '{key}'")
                else:
                    raise ValueError(f"Agent tried to use placeholder {self.PLACEHOLDER_FORMATTING_PLAN} but no plan is stored.")
            else:
                processed_input[key] = value
        return processed_input

    def _execute_tool(self, tool_name: str, tool_input_from_llm: str | dict) -> str:
        # tool_input_from_llm is what the LLM generated for "Action Input"
        # This will be the actual value passed as the 'tool_input' argument to the tool function,
        # after parsing and placeholder substitution.
        payload_value_for_tool = None

        if isinstance(tool_input_from_llm, str):
            parsed_llm_input_dict = None
            # LLM should provide a VALID JSON string for dictionary inputs.
            try:
                parsed_llm_input_dict = json.loads(tool_input_from_llm)
                print(f"  _execute_tool: Parsed LLM string input as JSON to dict.")
                payload_value_for_tool = self._substitute_placeholders(parsed_llm_input_dict)
            except json.JSONDecodeError:
                # If it's not a JSON dict string, treat as a simple string argument (e.g. for analyze_document_structure)
                # This might also catch cases where LLM provides a non-dict JSON literal (e.g. "just a string literal")
                payload_value_for_tool = tool_input_from_llm.strip('"').strip("'") # Strip potential quotes if it's a path
                print(f"  _execute_tool: LLM string input treated as simple string (JSON parse failed, after strip): {str(payload_value_for_tool)[:100]}...")

        elif isinstance(tool_input_from_llm, dict):
            # LangChain's ReAct parser might have already converted LLM's JSON string output into a dict.
            payload_value_for_tool = self._substitute_placeholders(tool_input_from_llm)
            print(f"  _execute_tool: LLM dict input, after subs: {str(payload_value_for_tool)[:100]}...")
        else:
            error_msg = f"LLM provided invalid type for Action Input: {type(tool_input_from_llm)}. Value: {str(tool_input_from_llm)[:200]}"
            print(f"  _execute_tool: {error_msg}")
            return json.dumps({"error": error_msg})

        # All our tools are defined as def tool_name(tool_input: str | dict).
        # LangChain's @tool will wrap this so invoke expects {"tool_input": <payload_value_for_tool>}
        args_for_langchain_invoke = {"tool_input": payload_value_for_tool} # Correct variable name

        selected_tool = next((t for t in self.tools if t.name == tool_name), None)
        if not selected_tool:
            return f"Error: Tool '{tool_name}' not found. Available tools: {[t.name for t in self.tools]}"

        try:
            print(f"  Invoking tool '{selected_tool.name}' with args for invoke: {str(args_for_langchain_invoke)[:200]}...") # Use correct variable
            observation = selected_tool.invoke(args_for_langchain_invoke) # Use correct variable
        except Exception as e:
            print(f"  Error executing tool {tool_name}: {e}")
            traceback.print_exc()
            return f"Error executing tool {tool_name}: {str(e)}"

        try:
            analysis_output_data = json.loads(observation) if isinstance(observation, str) else observation

            if tool_name == "analyze_document_structure" and isinstance(analysis_output_data, dict) and "document_path" in analysis_output_data:
                analyzed_path = analysis_output_data["document_path"]
                if analyzed_path == self.current_doc_path: # Check if it's the original document
                    self.full_original_analysis_json = observation
                    print(f"  Stored full_original_analysis_json (length {len(observation) if observation else 0})")
                elif analyzed_path == self.current_output_doc_path: # Check if it's the modified document
                    self.full_modified_analysis_json = observation
                    print(f"  Stored full_modified_analysis_json (length {len(observation) if observation else 0})")
            elif tool_name == "create_formatting_plan":
                self.current_formatting_plan_json = observation
                print(f"  Stored current_formatting_plan_json (length {len(observation) if observation else 0})")
        except json.JSONDecodeError:
            print(f"  Warning: Observation from {tool_name} was not valid JSON, not storing: {observation[:100]}")
        except Exception as e:
            print(f"  Error processing/storing observation from {tool_name}: {e}")

        return str(observation)

    def run(self, user_query: str, document_path: str, output_document_path: str = None):
        self.current_doc_path = document_path
        if not output_document_path:
            self.current_output_doc_path = document_path.replace(".docx", "_formatted.docx")
        else:
            self.current_output_doc_path = output_document_path

        self.full_original_analysis_json = None
        self.current_formatting_plan_json = None
        self.full_modified_analysis_json = None

        agent_initial_input = (
            f"User query: '{user_query}'.\n"
            f"The document to work on is: '{self.current_doc_path}'.\n"
            f"The output path for formatted document is: '{self.current_output_doc_path}'.\n"
            "Follow the general workflow: analyze original, create plan, apply plan, analyze modified, validate. Use placeholders like $FULL_ORIGINAL_ANALYSIS where instructed."
        )

        self.chat_history.append(HumanMessage(content=agent_initial_input))

        intermediate_steps = []
        max_iterations = 12 # INCREASED to allow for full validation flow

        for i in range(max_iterations):
            print(f"\n--- Iteration {i+1}/{max_iterations} ---")
            try:
                current_input_for_llm = agent_initial_input if i == 0 else "What is the next logical step based on the previous actions and observations?"

                current_agent_input_dict = {
                    "input": current_input_for_llm,
                    "intermediate_steps": intermediate_steps,
                    "chat_history": self.chat_history
                }

                print(f"Iteration {i+1}: Calling agent.invoke (LLM for next step planning) with input: \"{current_input_for_llm[:100]}...\"")
                llm_call_start_time = time.time()
                llm_output = self.agent.invoke(current_agent_input_dict)
                llm_call_duration = time.time() - llm_call_start_time
                print(f"Iteration {i+1}: agent.invoke returned after {llm_call_duration:.2f}s. Type: {type(llm_output)}")

                if isinstance(llm_output, AgentFinish):
                    final_answer = llm_output.return_values.get("output", "No final answer from AgentFinish.")
                    print(f"AgentFinish: {final_answer}")
                    self.chat_history.append(AIMessage(content=final_answer))
                    return final_answer

                if not isinstance(llm_output, AgentAction):
                    final_answer = str(llm_output)
                    if hasattr(llm_output, 'log'): print(f"LLM Log: {llm_output.log}")
                    if "Final Answer:" in final_answer :
                         final_answer = final_answer.split("Final Answer:")[-1].strip()
                    else:
                        print(f"Error: LLM output was not AgentAction or AgentFinish. Type: {type(llm_output)}, Output: {str(llm_output)[:500]}")
                        self.chat_history.append(AIMessage(content=f"Agent produced unexpected output type: {type(llm_output)}"))
                        return f"Agent error: Unexpected output type from LLM. Last output: {str(llm_output)[:500]}"

                agent_action = llm_output
                tool_name = agent_action.tool
                tool_input_from_llm = agent_action.tool_input

                print(f"LLM Action: {tool_name}, LLM Action Input: {str(tool_input_from_llm)[:200]}...")

                observation_str = self._execute_tool(tool_name, tool_input_from_llm)

                print(f"Observation from {tool_name} (full length {len(observation_str)} chars, first 100 shown): {observation_str[:100]}...")

                observation_str_for_scratchpad = observation_str
                MAX_OBS_LEN_SCRATCHPAD = 1000
                if len(observation_str_for_scratchpad) > MAX_OBS_LEN_SCRATCHPAD:
                    observation_str_for_scratchpad = observation_str_for_scratchpad[:MAX_OBS_LEN_SCRATCHPAD] + f"... (truncated, original length {len(observation_str)})"

                intermediate_steps.append((agent_action, observation_str_for_scratchpad))

            except Exception as e:
                error_message = f"Error in agent loop iteration {i+1}: {e}"
                print(error_message)
                traceback.print_exc()
                self.chat_history.append(AIMessage(content=f"Encountered an error: {error_message}"))
                return f"An error occurred in the agent loop: {e}"

        self.chat_history.append(AIMessage(content="Agent reached maximum iterations."))
        return "Agent reached maximum iterations."


if __name__ == '__main__':
    from docx import Document as PythonDocXDocument # Keep this import local to __main__
    sample_doc_path = "sample_doc_for_agent.docx"
    sample_output_path = "sample_doc_for_agent_formatted.docx"

    doc = PythonDocXDocument()
    doc.add_heading('Agent Test Document', level=0)
    doc.add_paragraph('This is paragraph one. It needs some formatting.')
    doc.add_heading('Section Alpha', level=1)
    doc.add_paragraph('This is paragraph two, under Section Alpha. It is a bit messy.')
    doc.save(sample_doc_path)
    print(f"Created '{sample_doc_path}' for agent testing.")

    try:
        formatter_agent = DocumentFormattingAgent()

        user_request = "Please make this document look more professional and fix inconsistencies."
        print(f"\n--- Running agent with query: '{user_request}' on '{sample_doc_path}' ---")

        result = formatter_agent.run(
            user_query=user_request,
            document_path=sample_doc_path,
            output_document_path=sample_output_path
        )

        print("\n--- Agent Result ---")
        print(result)

    except ValueError as ve:
        print(f"Setup Error: {ve}")
        # Ensure this matches the error from get_groq_api_key if key is truly missing after all checks
        if "GROQ_API_KEY is not set" in str(ve):
             print("Please ensure your GROQ_API_KEY is set in .env at the project root.")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")
        traceback.print_exc()
    finally:
        import os # Keep this local if only used here
        if os.path.exists(sample_doc_path):
            os.remove(sample_doc_path)
        if os.path.exists(sample_output_path):
            os.remove(sample_output_path)
        print(f"\nCleaned up '{sample_doc_path}' and '{sample_output_path}'.")
