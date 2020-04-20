require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Respond to a click event
    $("#getAnalyzers").on('click', "", function(e) {
    
        // Prevent drilldown from redirecting away from the page
        e.preventDefault();
    
        // Console feedback
        console.log("Refresh analyzers started"); 
    
	// Create a service and request a refresh for analyzers
        var service = mvc.createService();
        service.get('/services/TA_cortex_analyzers', "", function(err, response) {
    
            if(err) {
		// Something is not working during the recovering process
                $('#responseAnalyzers').text(response.err);
            }
            else if(response.status === 200) {
                console.log('Response: ', response.data);

		var now = new Date(parseFloat(response.data["updated"])*1000).toGMTString()
		// Set the updated time and confirm the reload
		$('#dateNow').text(now)
                $('#responseAnalyzers').text(response.data["result"]);

		// Update default AND submitted tokens
		var def_tokens = mvc.Components.get("default");
		var sub_tokens = mvc.Components.get("submitted");
                def_tokens.set("updated", response.data["updated"]);
                sub_tokens.set("updated", response.data["updated"]);


            }
	
            // Console feedback
            console.log("Refresh analyzers ended"); 

        })
    
    });

});

