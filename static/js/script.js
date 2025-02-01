$(document).ready(function() {
    let eventSource;
    let isStopped = false;
    let chatHistory = [];
    let aiResponseBuffer = "";

    function submitForm() {
        const prompt = $('#prompt').val();
        const $sendButton = $('#sendButton');
        const $chatMessages = $('#chat-messages');
        const $loadingSpinner = $('.loading-spinner');
        
        if (!prompt.trim()) {
            alert("Please enter a message.");
            return;
        }

        $sendButton.prop('disabled', true);
        $('.submit-text').hide();
        $loadingSpinner.show();
        isStopped = false;

        $chatMessages.append(`<div class="chat-message user-message">${prompt}</div>`);
        $('#prompt').val('');
        $chatMessages.scrollTop($chatMessages[0].scrollHeight);

        eventSource = new EventSource(`/get_response?prompt=${encodeURIComponent(prompt)}&chat_history=${encodeURIComponent(JSON.stringify(chatHistory))}`);
        console.log("EventSource created:", eventSource); // Log the EventSource object

        eventSource.onopen = function() {
            console.log("EventSource connection opened"); // Log when the connection is opened
        };

        eventSource.onmessage = function(event) {
            console.log("Received data:", event.data); // Log the received data
            if (isStopped) return;

            const data = event.data;
            if (data === '[DONE]') {
                console.log("Stream completed"); // Log stream completion
                eventSource.close();
                $sendButton.prop('disabled', false);
                $('.submit-text').show();
                $loadingSpinner.hide();

                if (aiResponseBuffer) {
                    console.log("Final AI response:", aiResponseBuffer); // Log the final response
                    const formattedResponse = marked.parse(aiResponseBuffer);
                    console.log("Formatted response:", formattedResponse); // Log the formatted response
                    $chatMessages.append(`<div class="chat-message ai-message">${formattedResponse}</div>`);
                    aiResponseBuffer = "";
                }

                $chatMessages.scrollTop($chatMessages[0].scrollHeight);
            } else {
                const parsedData = JSON.parse(data);
                if (parsedData.response) {
                    console.log("Received response chunk:", parsedData.response); // Log each response chunk
                    aiResponseBuffer += parsedData.response;
                } else if (parsedData.error) {
                    console.error("Error:", parsedData.error); // Log errors
                    $chatMessages.append(`<div class="chat-message ai-message text-danger">Error: ${parsedData.error}</div>`);
                    eventSource.close();
                }
            }
        };

        eventSource.onerror = function() {
            console.error("EventSource error"); // Log EventSource errors
            if (isStopped) return;

            $chatMessages.append(`<div class="chat-message ai-message text-danger">Error: Connection closed unexpectedly.</div>`);
            eventSource.close();
            $sendButton.prop('disabled', false);
            $('.submit-text').show();
            $loadingSpinner.hide();
        };
    }

    $('#prompt').on('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitForm();
        }
    });

    $('#sendButton').click(function(e) {
        e.preventDefault();
        submitForm();
    });

    $('#prompt').on('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Test Markdown rendering
    const testResponse = "Hello! How can I help you today?";
    const renderedResponse = marked.parse(testResponse);
    console.log("Test rendered response:", renderedResponse);
    $('#chat-messages').append(`<div class="chat-message ai-message">${renderedResponse}</div>`);
});
