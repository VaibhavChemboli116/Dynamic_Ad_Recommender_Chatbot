Dynamic Ad-Recommender Chatbot
This project is a Python-based chatbot that dynamically injects relevant, sponsored product advertisements into a conversation. It uses GPT-4o-mini to maintain a natural dialogue and to periodically judge the topical coherence of the conversation. If the conversation remains on a consistent topic, the chatbot uses SerpApi to find a relevant product and seamlessly appends it to its response.
Features
•	Conversational Tracking: Maintains a history of the user and AI messages to provide context for responses.
•	Topical Coherence Analysis: After every 4th user message, a GPT-4o-mini "judge" analyzes the last few exchanges to determine if they share a single, coherent topic.
•	Dynamic Ad Injection: If the conversation is deemed coherent, the bot suggests a relevant product, searches for it using the SerpApi Google Shopping engine, and appends a sponsored link to its response.
•	Streaming Completions: Utilizes streaming from the OpenAI API to ensure that answers are delivered smoothly and never cut off mid-sentence.
•	Thread-Safe Design: Built to be thread-safe without requiring complex background threading.
How It Works
The chatbot's logic is orchestrated by the AdRecommender class:
1.	Conversation Buffering: The bot stores the conversation history (alternating user questions and AI answers) in a buffer. This buffer has a configurable maximum size to manage memory.
2.	Triggering the Ad Logic: A counter tracks the number of user questions. When this counter reaches 4, the ad-recommendation logic is triggered.
3.	Judging Topical Coherence: A "snapshot" of the last 7 lines of the conversation is sent to a GPT-4o-mini model acting as a judge. This judge is prompted to determine two things:
o	Is the conversation on a single topic? (RELATED: yes/no)
o	If yes, what is the topic and a suitable product/service? (TOPIC: <topic>, P/S: <product>)
4.	Searching for Products: If the judge confirms the conversation is related and suggests a product, the bot queries the SerpApi Google Shopping API for that product.
5.	Injecting the Ad: If a relevant product with a link is found, it is formatted into a markdown link and appended to the AI's primary response. The ad includes the product name, a direct link, and a short description.
6.	Resetting: The user message counter is reset to 0, and the cycle continues. An ad can potentially be shown every 4 user questions if the topic remains coherent.

Usage
To run the chatbot, simply execute the Python script from your terminal:
python ad_recommender.py

You can then interact with the chatbot directly in your console. Type quit to exit the program.
Configuration
You can modify the following constants at the top of the ad_recommender.py file to change the bot's behavior:
•	DEBUG: Set to False to silence debug prints.
•	OPENAI_MODEL: Change the GPT model used for chat and judging.
•	GPT_MAX_TOKENS: Adjust the maximum length of the AI's response.
•	MAX_BUFFER_SIZE: Change the number of conversation lines kept in memory.
•	TRIGGER_QS: Modify how many user questions trigger the ad check.
•	SNAPSHOT_LINES: Adjust the number of lines sent to the topic judge.

<img width="468" height="646" alt="image" src="https://github.com/user-attachments/assets/b0df8be5-2a33-4212-b1f4-088190c4868e" />
