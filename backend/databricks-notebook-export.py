# Databricks notebook source
# MAGIC %md
# MAGIC #Tool-calling Agent
# MAGIC
# MAGIC This is an auto-generated notebook created by an AI Playground export.
# MAGIC
# MAGIC This notebook uses [Mosaic AI Agent Framework](https://docs.databricks.com/generative-ai/agent-framework/build-genai-apps.html) to recreate your agent from the AI Playground. It  demonstrates how to develop, manually test, evaluate, log, and deploy a tool-calling agent in LangGraph.
# MAGIC
# MAGIC The agent code implements [MLflow's ChatAgent](https://mlflow.org/docs/latest/python_api/mlflow.pyfunc.html#mlflow.pyfunc.ChatAgent) interface, a Databricks-recommended open-source standard that simplifies authoring multi-turn conversational agents, and is fully compatible with Mosaic AI agent framework functionality.
# MAGIC
# MAGIC  **_NOTE:_**  This notebook uses LangChain, but AI Agent Framework is compatible with any agent authoring framework, including LlamaIndex or pure Python agents written with the OpenAI SDK.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - Address all `TODO`s in this notebook.

# COMMAND ----------

# MAGIC %pip install -U -qqqq mlflow langchain langgraph==0.3.4 databricks-langchain pydantic databricks-agents unitycatalog-langchain[databricks] uv
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md ## Define the agent in code
# MAGIC Below we define our agent code in a single cell, enabling us to easily write it to a local Python file for subsequent logging and deployment using the `%%writefile` magic command.
# MAGIC
# MAGIC For more examples of tools to add to your agent, see [docs](https://docs.databricks.com/generative-ai/agent-framework/agent-tool.html).

# COMMAND ----------

# MAGIC %%writefile agent.py
# MAGIC from typing import Any, Generator, Optional, Sequence, Union
# MAGIC
# MAGIC import mlflow
# MAGIC from databricks_langchain import (
# MAGIC     ChatDatabricks,
# MAGIC     VectorSearchRetrieverTool,
# MAGIC     DatabricksFunctionClient,
# MAGIC     UCFunctionToolkit,
# MAGIC     set_uc_function_client,
# MAGIC )
# MAGIC from langchain_core.language_models import LanguageModelLike
# MAGIC from langchain_core.runnables import RunnableConfig, RunnableLambda
# MAGIC from langchain_core.tools import BaseTool
# MAGIC from langgraph.graph import END, StateGraph
# MAGIC from langgraph.graph.graph import CompiledGraph
# MAGIC from langgraph.graph.state import CompiledStateGraph
# MAGIC from langgraph.prebuilt.tool_node import ToolNode
# MAGIC from mlflow.langchain.chat_agent_langgraph import ChatAgentState, ChatAgentToolNode
# MAGIC from mlflow.pyfunc import ChatAgent
# MAGIC from mlflow.types.agent import (
# MAGIC     ChatAgentChunk,
# MAGIC     ChatAgentMessage,
# MAGIC     ChatAgentResponse,
# MAGIC     ChatContext,
# MAGIC )
# MAGIC
# MAGIC mlflow.langchain.autolog()
# MAGIC
# MAGIC client = DatabricksFunctionClient()
# MAGIC set_uc_function_client(client)
# MAGIC
# MAGIC ############################################
# MAGIC # Define your LLM endpoint and system prompt
# MAGIC ############################################
# MAGIC LLM_ENDPOINT_NAME = "databricks-claude-sonnet-4"
# MAGIC llm = ChatDatabricks(endpoint=LLM_ENDPOINT_NAME)
# MAGIC
# MAGIC system_prompt = """You are a knowledgeable and compassionate pregnancy support assistant. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth. Your knowledge covers prenatal care, fetal development, common pregnancy symptoms and concerns, nutrition and lifestyle recommendations, medical screenings and tests, labor and delivery preparation, and postpartum care.
# MAGIC
# MAGIC Key responsibilities:
# MAGIC
# MAGIC Offer trimester-specific advice and milestones to expect
# MAGIC Provide evidence-based information on prenatal nutrition and safe exercise
# MAGIC Explain common pregnancy symptoms and when to seek medical attention
# MAGIC Guide users through recommended medical appointments and screenings
# MAGIC Offer emotional support and resources for mental health during pregnancy
# MAGIC Educate on fetal development stages
# MAGIC Assist with birth plan creation and labor preparation
# MAGIC Provide information on breastfeeding and early postpartum care
# MAGIC Always encourage users to consult with their healthcare provider for personalized medical advice. Be sensitive to diverse family structures and cultural backgrounds. Maintain a warm, supportive tone while providing factual, scientific information. If asked about anything outside your scope of knowledge, refer users to appropriate medical professionals or reputable pregnancy resources.
# MAGIC
# MAGIC The agent help select a healthcare provider using the tools provide using location and accessibility coverage and accessibility as criteria. once a provider is selected the agent should use the tool context to keep track of upcoming appointments  and provide expectations for those appointments 
# MAGIC
# MAGIC SC
# MAGIC Certainly! I'll modify the system prompt to include those important functionalities. Here's an updated version:
# MAGIC
# MAGIC You are a knowledgeable and compassionate pregnancy support assistant with advanced capabilities to help users select healthcare providers and manage appointments. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth.
# MAGIC
# MAGIC Key responsibilities:
# MAGIC
# MAGIC Assist in selecting healthcare providers:
# MAGIC
# MAGIC Use provided tools to search for providers based on user's location
# MAGIC Consider insurance coverage and accessibility as key criteria
# MAGIC Present options and help users compare providers
# MAGIC Appointment management:
# MAGIC
# MAGIC Use the tool context to track and remind users of upcoming appointments
# MAGIC Provide detailed expectations for each appointment type
# MAGIC Offer preparation tips for specific screenings or tests
# MAGIC Offer trimester-specific advice and milestones
# MAGIC
# MAGIC Provide evidence-based information on prenatal nutrition and safe exercise
# MAGIC
# MAGIC Explain common pregnancy symptoms and when to seek medical attention
# MAGIC
# MAGIC Guide users through recommended medical appointments and screenings
# MAGIC
# MAGIC Offer emotional support and resources for mental health during pregnancy
# MAGIC
# MAGIC Educate on fetal development stages
# MAGIC
# MAGIC Assist with birth plan creation and labor preparation
# MAGIC
# MAGIC Provide information on breastfeeding and early postpartum care
# MAGIC
# MAGIC When helping select a provider:
# MAGIC
# MAGIC Ask for the user's location, insurance details, and any specific needs or preferences
# MAGIC Use the provider search tool to generate a list of suitable options
# MAGIC Present the options clearly, highlighting key factors like distance, ratings, and specialties
# MAGIC Assist in scheduling the first appointment with the chosen provider
# MAGIC For appointment management:
# MAGIC
# MAGIC Maintain an up-to-date calendar of the user's scheduled appointments
# MAGIC Send reminders before each appointment
# MAGIC Provide a brief overview of what to expect at each appointment type (e.g., first trimester screening, glucose test, etc.)
# MAGIC Suggest questions the user might want to ask their provider
# MAGIC Always encourage users to consult with their healthcare provider for personalized medical advice. Be sensitive to diverse family structures and cultural backgrounds. Maintain a warm, supportive tone while providing factual, scientific information. If asked about anything outside your scope of knowledge, refer users to appropriate medical professionals or reputable pregnancy resources."""
# MAGIC
# MAGIC ###############################################################################
# MAGIC ## Define tools for your agent, enabling it to retrieve data or take actions
# MAGIC ## beyond text generation
# MAGIC ## To create and see usage examples of more tools, see
# MAGIC ## https://docs.databricks.com/generative-ai/agent-framework/agent-tool.html
# MAGIC ###############################################################################
# MAGIC tools = []
# MAGIC
# MAGIC # You can use UDFs in Unity Catalog as agent tools
# MAGIC uc_tool_names = []
# MAGIC uc_toolkit = UCFunctionToolkit(function_names=uc_tool_names)
# MAGIC tools.extend(uc_toolkit.tools)
# MAGIC
# MAGIC
# MAGIC # # (Optional) Use Databricks vector search indexes as tools
# MAGIC # # See https://docs.databricks.com/generative-ai/agent-framework/unstructured-retrieval-tools.html
# MAGIC # # for details
# MAGIC #
# MAGIC # # TODO: Add vector search indexes as tools or delete this block
# MAGIC # vector_search_tools = [
# MAGIC #         VectorSearchRetrieverTool(
# MAGIC #         index_name="",
# MAGIC #         # filters="..."
# MAGIC #     )
# MAGIC # ]
# MAGIC # tools.extend(vector_search_tools)
# MAGIC
# MAGIC
# MAGIC #####################
# MAGIC ## Define agent logic
# MAGIC #####################
# MAGIC
# MAGIC
# MAGIC def create_tool_calling_agent(
# MAGIC     model: LanguageModelLike,
# MAGIC     tools: Union[Sequence[BaseTool], ToolNode],
# MAGIC     system_prompt: Optional[str] = None,
# MAGIC ) -> CompiledGraph:
# MAGIC     model = model.bind_tools(tools)
# MAGIC
# MAGIC     # Define the function that determines which node to go to
# MAGIC     def should_continue(state: ChatAgentState):
# MAGIC         messages = state["messages"]
# MAGIC         last_message = messages[-1]
# MAGIC         # If there are function calls, continue. else, end
# MAGIC         if last_message.get("tool_calls"):
# MAGIC             return "continue"
# MAGIC         else:
# MAGIC             return "end"
# MAGIC
# MAGIC     if system_prompt:
# MAGIC         preprocessor = RunnableLambda(
# MAGIC             lambda state: [{"role": "system", "content": system_prompt}]
# MAGIC             + state["messages"]
# MAGIC         )
# MAGIC     else:
# MAGIC         preprocessor = RunnableLambda(lambda state: state["messages"])
# MAGIC     model_runnable = preprocessor | model
# MAGIC
# MAGIC     def call_model(
# MAGIC         state: ChatAgentState,
# MAGIC         config: RunnableConfig,
# MAGIC     ):
# MAGIC         response = model_runnable.invoke(state, config)
# MAGIC
# MAGIC         return {"messages": [response]}
# MAGIC
# MAGIC     workflow = StateGraph(ChatAgentState)
# MAGIC
# MAGIC     workflow.add_node("agent", RunnableLambda(call_model))
# MAGIC     workflow.add_node("tools", ChatAgentToolNode(tools))
# MAGIC
# MAGIC     workflow.set_entry_point("agent")
# MAGIC     workflow.add_conditional_edges(
# MAGIC         "agent",
# MAGIC         should_continue,
# MAGIC         {
# MAGIC             "continue": "tools",
# MAGIC             "end": END,
# MAGIC         },
# MAGIC     )
# MAGIC     workflow.add_edge("tools", "agent")
# MAGIC
# MAGIC     return workflow.compile()
# MAGIC
# MAGIC
# MAGIC class LangGraphChatAgent(ChatAgent):
# MAGIC     def __init__(self, agent: CompiledStateGraph):
# MAGIC         self.agent = agent
# MAGIC
# MAGIC     def predict(
# MAGIC         self,
# MAGIC         messages: list[ChatAgentMessage],
# MAGIC         context: Optional[ChatContext] = None,
# MAGIC         custom_inputs: Optional[dict[str, Any]] = None,
# MAGIC     ) -> ChatAgentResponse:
# MAGIC         request = {"messages": self._convert_messages_to_dict(messages)}
# MAGIC
# MAGIC         messages = []
# MAGIC         for event in self.agent.stream(request, stream_mode="updates"):
# MAGIC             for node_data in event.values():
# MAGIC                 messages.extend(
# MAGIC                     ChatAgentMessage(**msg) for msg in node_data.get("messages", [])
# MAGIC                 )
# MAGIC         return ChatAgentResponse(messages=messages)
# MAGIC
# MAGIC     def predict_stream(
# MAGIC         self,
# MAGIC         messages: list[ChatAgentMessage],
# MAGIC         context: Optional[ChatContext] = None,
# MAGIC         custom_inputs: Optional[dict[str, Any]] = None,
# MAGIC     ) -> Generator[ChatAgentChunk, None, None]:
# MAGIC         request = {"messages": self._convert_messages_to_dict(messages)}
# MAGIC         for event in self.agent.stream(request, stream_mode="updates"):
# MAGIC             for node_data in event.values():
# MAGIC                 yield from (
# MAGIC                     ChatAgentChunk(**{"delta": msg}) for msg in node_data["messages"]
# MAGIC                 )
# MAGIC
# MAGIC
# MAGIC # Create the agent object, and specify it as the agent object to use when
# MAGIC # loading the agent back for inference via mlflow.models.set_model()
# MAGIC agent = create_tool_calling_agent(llm, tools, system_prompt)
# MAGIC AGENT = LangGraphChatAgent(agent)
# MAGIC mlflow.models.set_model(AGENT)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test the agent
# MAGIC
# MAGIC Interact with the agent to test its output. Since this notebook called `mlflow.langchain.autolog()` you can view the trace for each step the agent takes.
# MAGIC
# MAGIC Replace this placeholder input with an appropriate domain-specific example for your agent.

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from agent import AGENT

AGENT.predict({"messages": [{"role": "user", "content": "Hello!"}]})

# COMMAND ----------

for event in AGENT.predict_stream(
    {"messages": [{"role": "user", "content": "What is 5+5 in python"}]}
):
    print(event, "-----------\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Log the `agent` as an MLflow model
# MAGIC Determine Databricks resources to specify for automatic auth passthrough at deployment time
# MAGIC - **TODO**: If your Unity Catalog Function queries a [vector search index](https://docs.databricks.com/generative-ai/agent-framework/unstructured-retrieval-tools.html) or leverages [external functions](https://docs.databricks.com/generative-ai/agent-framework/external-connection-tools.html), you need to include the dependent vector search index and UC connection objects, respectively, as resources. See [docs](https://docs.databricks.com/generative-ai/agent-framework/log-agent.html#specify-resources-for-automatic-authentication-passthrough) for more details.
# MAGIC
# MAGIC Log the agent as code from the `agent.py` file. See [MLflow - Models from Code](https://mlflow.org/docs/latest/models.html#models-from-code).

# COMMAND ----------

# Determine Databricks resources to specify for automatic auth passthrough at deployment time
import mlflow
from agent import tools, LLM_ENDPOINT_NAME
from databricks_langchain import VectorSearchRetrieverTool
from mlflow.models.resources import DatabricksFunction, DatabricksServingEndpoint
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool

resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT_NAME)]
for tool in tools:
    if isinstance(tool, VectorSearchRetrieverTool):
        resources.extend(tool.resources)
    elif isinstance(tool, UnityCatalogTool):
        # TODO: If the UC function includes dependencies like external connection or vector search, please include them manually.
        # See the TODO in the markdown above for more information.
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))

input_example = {
    "messages": [
        {
            "role": "user",
            "content": "Hello"
        }
    ]
}

with mlflow.start_run():
    logged_agent_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model="agent.py",
        input_example=input_example,
        resources=resources,
        extra_pip_requirements=[
            "databricks-connect"
        ]
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluate the agent with [Agent Evaluation](https://docs.databricks.com/generative-ai/agent-evaluation/index.html)
# MAGIC
# MAGIC You can edit the requests or expected responses in your evaluation dataset and run evaluation as you iterate your agent, leveraging mlflow to track the computed quality metrics.
# MAGIC
# MAGIC To evaluate your tool calls, try adding [custom metrics](https://docs.databricks.com/generative-ai/agent-evaluation/custom-metrics.html#evaluating-tool-calls).

# COMMAND ----------

import pandas as pd

eval_examples = [
    {
        "request": {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a knowledgeable and compassionate pregnancy support assistant. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth. Your knowledge covers prenatal care, fetal development, common pregnancy symptoms and concerns, nutrition and lifestyle recommendations, medical screenings and tests, labor and delivery preparation, and postpartum care.\n\nKey responsibilities:\n\nOffer trimester-specific advice and milestones to expect\nProvide evidence-based information on prenatal nutrition and safe exercise\nExplain common pregnancy symptoms and when to seek medical attention\nGuide users through recommended medical appointments and screenings\nOffer emotional support and resources for mental health during pregnancy\nEducate on fetal development stages\nAssist with birth plan creation and labor preparation\nProvide information on breastfeeding and early postpartum care\nAlways encourage users to consult with their healthcare provider for personalized medical advice. Be sensitive to diverse family structures and cultural backgrounds. Maintain a warm, supportive tone while providing factual, scientific information. If asked about anything outside your scope of knowledge, refer users to appropriate medical professionals or reputable pregnancy resources.\n\nThe agent help select a healthcare provider using the tools provide using location and accessibility coverage and accessibility as criteria. once a provider is selected the agent should use the tool context to keep track of upcoming appointments  and provide expectations for those appointments \n\nSC\nCertainly! I'll modify the system prompt to include those important functionalities. Here's an updated version:\n\nYou are a knowledgeable and compassionate pregnancy support assistant with advanced capabilities to help users select healthcare providers and manage appointments. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth.\n\nKey responsibilities:\n\nAssist in selecting healthcare providers:\n\nUse provided tools to search for providers based on user's location\nConsider insurance coverage and accessibility as key criteria\nPresent options and help users compare providers\nAppointment management:\n\nUse the tool context to track and remind users of upcoming appointments\nProvide detailed expectations for each appointment type\nOffer preparation tips for specific screenings or tests\nOffer trimester-specific advice and milestones\n\nProvide evidence-based information on prenatal nutrition and safe exercise\n\nExplain common pregnancy symptoms and when to seek medical attention\n\nGuide users through recommended medical appointments and screenings\n\nOffer emotional support and resources for mental health during pregnancy\n\nEducate on fetal development stages\n\nAssist with birth plan creation and labor preparation\n\nProvide information on breastfeeding and early postpartum care\n\nWhen helping select a provider:\n\nAsk for the user's location, insurance details, and any specific needs or preferences\nUse the provider search tool to generate a list of suitable options\nPresent the options clearly, highlighting key factors like distance, ratings, and specialties\nAssist in scheduling the first appointment with the chosen provider\nFor appointment management:\n\nMaintain an up-to-date calendar of the user's scheduled appointments\nSend reminders before each appointment\nProvide a brief overview of what to expect at each appointment type (e.g., first trimester screening, glucose test, etc.)\nSuggest questions the user might want to ask their provider\nAlways encourage users to consult with their healthcare provider for personalized medical advice. Be sensitive to diverse family structures and cultural backgrounds. Maintain a warm, supportive tone while providing factual, scientific information. If asked about anything outside your scope of knowledge, refer users to appropriate medical professionals or reputable pregnancy resources."
                },
                {
                    "role": "user",
                    "content": "Hello"
                }
            ]
        },
        "expected_response": None
    }
]

eval_dataset = pd.DataFrame(eval_examples)
display(eval_dataset)


# COMMAND ----------

import mlflow

with mlflow.start_run(run_id=logged_agent_info.run_id):
    eval_results = mlflow.evaluate(
        f"runs:/{logged_agent_info.run_id}/agent",
        data=eval_dataset,  # Your evaluation dataset
        model_type="databricks-agent",  # Enable Mosaic AI Agent Evaluation
    )

# Review the evaluation results in the MLFLow UI (see console output), or access them in place:
display(eval_results.tables['eval_results'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Perform pre-deployment validation of the agent
# MAGIC Before registering and deploying the agent, we perform pre-deployment checks via the [mlflow.models.predict()](https://mlflow.org/docs/latest/python_api/mlflow.models.html#mlflow.models.predict) API. See [documentation](https://docs.databricks.com/machine-learning/model-serving/model-serving-debug.html#validate-inputs) for details

# COMMAND ----------

mlflow.models.predict(
    model_uri=f"runs:/{logged_agent_info.run_id}/agent",
    input_data={"messages": [{"role": "user", "content": "Hello!"}]},
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Register the model to Unity Catalog
# MAGIC
# MAGIC Update the `catalog`, `schema`, and `model_name` below to register the MLflow model to Unity Catalog.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

# TODO: define the catalog, schema, and model name for your UC model
catalog = ""
schema = ""
model_name = ""
UC_MODEL_NAME = f"{catalog}.{schema}.{model_name}"

# register the model to UC
uc_registered_model_info = mlflow.register_model(
    model_uri=logged_agent_info.model_uri, name=UC_MODEL_NAME
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy the agent

# COMMAND ----------

from databricks import agents
agents.deploy(UC_MODEL_NAME, uc_registered_model_info.version, tags = {"endpointSource": "playground"})

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next steps
# MAGIC
# MAGIC After your agent is deployed, you can chat with it in AI playground to perform additional checks, share it with SMEs in your organization for feedback, or embed it in a production application. See [docs](https://docs.databricks.com/generative-ai/deploy-agent.html) for details