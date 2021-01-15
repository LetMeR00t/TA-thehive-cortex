require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Console feedback
    console.log("Getting global accounts..."); 

 
    // Create a service and request a refresh for analyzers
    var service = mvc.createService();
    service.get('TA_thehive_cortex_account', "", function(err, response) {
 
        if(err) {
    	// Something is not working during the recovering process
            console.log(response.err);
        }
        else if(response.status === 200) {
            console.log('Response: ', response.data);
 
    	    var def_tokens = mvc.Components.get("default");
    	    var sub_tokens = mvc.Components.get("submitted");
            var accounts = [];
            var entries = response.data["entry"];

	    entries.forEach(entry => accounts.push(entry["name"]));
 
            def_tokens.set("global_accounts", accounts.join(","));
            sub_tokens.set("global_accounts", accounts.join(","));
			
        }
    
        // Console feedback
        console.log("Global accounts recovered"); 
 
    })

});

