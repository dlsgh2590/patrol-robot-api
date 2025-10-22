// 지도 초기화
const map = L.map('map').setView([37.5665, 126.9780], 16); // 서울 기준
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let marker = null;

async function loadRobotStatus() {
  const token = localStorage.getItem("token");
  const res = await fetch("http://localhost:8000/robot/status", {
    headers: { "Authorization": `Bearer ${token}` }
  });
  const data = await res.json();

  document.getElementById("battery").innerText = data.battery;
  document.getElementById("position").innerText = `${data.lat}, ${data.lon}`;

  if (marker) map.removeLayer(marker);
  marker = L.marker([data.lat, data.lon]).addTo(map);
}

// 5초마다 갱신
setInterval(loadRobotStatus, 5000);

function startPatrol() {
  fetch("http://localhost:8000/robot/start", {
    method: "POST",
    headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` },
  });
}

function returnBase() {
  fetch("http://localhost:8000/robot/return", {
    method: "POST",
    headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` },
  });
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "login.html";
}

loadRobotStatus();
