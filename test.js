fetch("http://127.0.0.1:8000/users", {
    method: "GET",
    headers: {
        "Origin": "http://localhost:3000"  
    }
})
.then(response => {
    console.log("Status HTTP:", response.status);
    console.log("Access-Control-Allow-Origin:", response.headers.get("access-control-allow-origin") || "None");
    return response.json(); 
})
.then(data => {
    console.log("Données reçues:", data);
})
.catch(error => {
    console.error("Erreur:", error);
});