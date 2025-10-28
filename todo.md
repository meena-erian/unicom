Top issues and todo:
[X] Messages with action buttons are only supported on Telegram. There has to be an abstract crossplatform wrapper that works on WebChat too.
[X] Poor UI issue: tool calls and tool responses look very ugly and big in webchat.
[X] Message context chain is broken: Currently, when a user responds on webchat, the reply_to_message isn't even set, and as a results, the bot doesn't include any previous messages in the context. Add feature where users can branch conversations in chats, by their message, where on the UI, it would look like the user edited their message and now their message shows some navigation buttons to go back and forth between different version of the message, but in the database, the new version of the message is actually a separate message sent with reply_to_message set to the same reply_to_message value of the message they're editing (which could be null if its a first message in a chat)
[X] Performance critical issue: whenever a temporary disconnection occurs, the WebChat fallsback permanatly to polling mode until the user relads the page. This can risk server performance and client satisfaction. it should instead periodically try to reconnect to the websocket. 

Others:
[X] Add feature where users can delete their chats in WebChat
[X] improve scalability by adding web sockets at least just for incoming messages so no need for repetitive polling.
[ ] ensure chat list as well as message list in a chat are loaded with a limit with pagination 
[ ] Add font awesome and emojies to webchat 
[ ] UX Issue: When a user sends a message to the webview, it doesn't look like much is going on for a second or so until the bot responds. Users get impatient quickly if it doesn't at least show some sort of loading indicator or typing or something.