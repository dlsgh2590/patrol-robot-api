// 🚨 중요: 로봇의 ROS Bridge 서버 주소로 변경해야 합니다.
const ROSBRIDGE_SERVER_IP = "192.168.0.100";
const ROSBRIDGE_PORT = 9090;

const CAM_HOST = "192.168.0.100"; // Raspberry Pi (web_video_server)
const MJPEG_STREAM_URL = `http://${CAM_HOST}:8080/stream?topic=/image_raw&type=ros_compressed&width=640&height=480&quality=50`;

const ros = new ROSLIB.Ros({
  url: `ws://${ROSBRIDGE_SERVER_IP}:${ROSBRIDGE_PORT}`,
});

// DOM 요소
const statusIndicator = document.getElementById("status-indicator");
const statusText = document.getElementById("status-text");
const robotStatusElement = document.getElementById("metric-status");
const mapMain = document.getElementById("map-main");
const mapCanvas = document.getElementById("map-canvas");
const mapContainer = mapCanvas.closest(".w-full.h-full"); // 캔버스를 감싸는 컨테이너
const videoMain = document.getElementById("video-main");
const webcamFeed = document.getElementById("webcam-feed");
const webcamSmallFeed = document.getElementById("webcam-small-feed");
const patrolControlMap = document.getElementById("patrol-control-map");
const robotLocationCard = document.getElementById("robot-location-card");
const manualControl = document.getElementById("manual-control");

// 전역 변수
let isVideoRunning = false;
let currentMainView = "map";
let isDrawingPatrolArea = false; // 순찰 구역 그리기 모드 활성화 여부
let patrolAreaPoints = []; // 캔버스 픽셀 좌표 저장 배열: [{x: pX, y: pY}, ...]

const statusConfigs = {
  순찰중: { class: "bg-green-200 text-green-800", icon: "fas fa-route" },
  복귀중: { class: "bg-indigo-200 text-indigo-800", icon: "fas fa-home" },
  충전중: {
    class: "bg-blue-200 text-blue-800",
    icon: "fas fa-charging-station",
  },
  정지: { class: "bg-red-200 text-red-800", icon: "fas fa-stop-circle" },
  임무완료: {
    class: "bg-teal-200 text-teal-800",
    icon: "fas fa-check-circle",
  },
  "대기 중": {
    class: "bg-gray-200 text-gray-800",
    icon: "fas fa-ellipsis-h",
  },
  "연결 오류": {
    class: "bg-red-200 text-red-800",
    icon: "fas fa-exclamation-triangle",
  },
  "연결 끊김": {
    class: "bg-yellow-200 text-yellow-800",
    icon: "fas fa-plug",
  },
};

// ====================================================================
// ROS Bridge 연결 상태 처리
// ====================================================================

ros.on("connection", () => {
  console.log("ROS Bridge에 성공적으로 연결되었습니다.");
  statusIndicator.classList.replace("bg-red-500", "bg-green-500");
  statusText.textContent = "ROS 연결됨";
  statusText.classList.replace("text-red-700", "text-green-700");

  updateRobotStatus("대기 중");

  subscribeToTopics();
  // toggleVideoFeed(true); // 초기 로드 시 스트리밍 시작은 사용자의 원래 의도에 따라 주석 처리
});

ros.on("error", (error) => {
  console.error("ROS Bridge 연결 오류:", error);
  statusIndicator.classList.replace("bg-green-500", "bg-red-500");
  statusText.textContent = "ROS 오류 발생";
  statusText.classList.replace("text-green-700", "text-red-700");
  updateRobotStatus("연결 오류");
});

ros.on("close", () => {
  console.log("ROS Bridge 연결이 끊어졌습니다.");
  statusIndicator.classList.replace("bg-green-500", "bg-yellow-500");
  statusText.textContent = "ROS 연결 끊김";
  statusText.classList.replace("text-green-700", "text-yellow-700");
  updateRobotStatus("연결 끊김");
});

function updateRobotStatus(statusKey) {
  const config = statusConfigs[statusKey] || statusConfigs["대기 중"];
  robotStatusElement.innerHTML = `<i class="${config.icon} mr-3"></i> ${statusKey}`;
  robotStatusElement.className = "status-badge " + config.class;
}

// ====================================================================
// 토픽 구독 (데이터 수신) - 시뮬레이션 포함
// ====================================================================

function subscribeToTopics() {
  // 더미 상태 시뮬레이션
  const dummyStates = [
    "순찰중",
    "순찰중",
    "순찰중",
    "복귀중",
    "충전중",
    "임무완료",
    "정지",
  ];
  let currentDummyIndex = 0;
  setInterval(() => {
    if (!ros.isConnected) {
      // ROS 연결이 끊어졌을 때만 더미 상태를 사용 (연결 상태 시뮬레이션)
      const state = dummyStates[currentDummyIndex];
      updateRobotStatus(state);
      currentDummyIndex = (currentDummyIndex + 1) % dummyStates.length;

      // 더미 로봇 위치 업데이트
      const dummyX = (Math.random() * 20 - 10).toFixed(2);
      const dummyY = (Math.random() * 20 - 10).toFixed(2);
      document.getElementById(
        "robot-location"
      ).textContent = `X=${dummyX} m, Y=${dummyY} m (Dummy)`;
    }

    // 더미 메트릭 및 센서 값 업데이트
    let currentBattery =
      parseFloat(
        document.getElementById("metric-battery").textContent.replace("%", "")
      ) || 95;
    let currentDistance =
      parseFloat(
        document.getElementById("metric-distance").textContent.replace(" m", "")
      ) || 15.0;
    let currentTime =
      parseInt(
        document.getElementById("metric-time").textContent.replace(" min", "")
      ) || 120;
    let currentTemp =
      parseFloat(
        document.getElementById("metric-temp").textContent.replace(" °C", "")
      ) || 24.5;
    let currentHumi =
      parseFloat(
        document.getElementById("metric-humi").textContent.replace(" %", "")
      ) || 55.0;
    let currentCo2 =
      parseInt(
        document.getElementById("metric-co2").textContent.replace(" ppm", "")
      ) || 450;
    let currentTvoc =
      parseInt(
        document.getElementById("metric-tvoc").textContent.replace(" ppb", "")
      ) || 250;

    document.getElementById("metric-battery").textContent = `${(currentBattery >
    70
      ? currentBattery - 1
      : 95
    ).toFixed(0)}%`;
    document.getElementById("metric-distance").textContent = `${(
      currentDistance + 0.1
    ).toFixed(1)} m`;
    document.getElementById("metric-time").textContent = `${
      currentTime + 1
    } min`;
    document.getElementById("metric-temp").textContent = `${(
      currentTemp +
      Math.random() * 0.2 -
      0.1
    ).toFixed(1)} °C`;
    document.getElementById("metric-humi").textContent = `${(
      currentHumi +
      Math.random() * 0.5 -
      0.25
    ).toFixed(1)} %`;
    document.getElementById("metric-co2").textContent = `${Math.floor(
      currentCo2 + Math.random() * 5 - 2
    )} ppm`;
    document.getElementById("metric-tvoc").textContent = `${Math.floor(
      currentTvoc + Math.random() * 5 - 2
    )} ppb`;
  }, 5000);

  console.log("로봇 데이터 토픽 구독 준비 완료.");
}

// ====================================================================
// 동적 뷰 전환 및 웹캠 제어 (수정 복원됨)
// ====================================================================

window.toggleMainView = function (view) {
  if (view === currentMainView) return;
  // 뷰 전환 시 구역 그리기 모드 중이라면 반드시 비활성화
  if (isDrawingPatrolArea) stopDrawingPatrolArea(true);

  if (view === "map") {
    mapMain.classList.remove("hidden");
    videoMain.classList.add("hidden");
    document.getElementById("map-small").classList.add("hidden");
    document.getElementById("video-small").classList.remove("hidden");
    patrolControlMap.classList.remove("hidden");
    robotLocationCard.classList.remove("hidden");
    manualControl.classList.add("hidden");
    currentMainView = "map";
  } else if (view === "video") {
    videoMain.classList.remove("hidden");
    mapMain.classList.add("hidden");
    document.getElementById("video-small").classList.add("hidden");
    document.getElementById("map-small").classList.remove("hidden");
    manualControl.classList.remove("hidden");
    patrolControlMap.classList.add("hidden");
    robotLocationCard.classList.add("hidden");
    currentMainView = "video";
  }
};

window.toggleVideoFeed = function () {
  const button = document.querySelector(
    '.btn-action[onclick="toggleVideoFeed()"]'
  );

  if (!isVideoRunning) {
    // 스트리밍 시작
    webcamFeed.src = MJPEG_STREAM_URL;
    webcamSmallFeed.src = MJPEG_STREAM_URL;
    document.getElementById("video-placeholder").classList.add("hidden");
    button.innerHTML =
      '<i class="fas fa-camera-slash mr-2"></i> 웹 스트리밍 중지';
    button.classList.replace("bg-blue-500", "bg-red-500");
    button.classList.replace("hover:bg-blue-600", "hover:bg-red-600");
    isVideoRunning = true;
    customAlert("웹캠 스트리밍을 시작했습니다.");
  } else {
    // 스트리밍 중지
    webcamFeed.src = "";
    webcamSmallFeed.src = "";
    document.getElementById("video-placeholder").classList.remove("hidden");
    button.innerHTML = '<i class="fas fa-camera mr-2"></i> 웹 스트리밍 시작';
    button.classList.replace("bg-red-500", "bg-blue-500");
    button.classList.replace("hover:bg-red-600", "hover:bg-blue-600");
    isVideoRunning = false;
    customAlert("웹캠 스트리밍을 중지했습니다.");
  }
};

// ====================================================================
// 순찰 구역 설정 (폴리곤) 로직 - 최종 확정 부분
// ====================================================================

// 캔버스 마우스 클릭 이벤트 리스너 (웨이포인트 지정)
const handleMapClick = (e) => {
  if (!isDrawingPatrolArea) return;

  // 캔버스 내에서의 상대적인 좌표 계산
  const rect = mapCanvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  patrolAreaPoints.push({ x: x, y: y });

  drawPatrolArea();

  // 3개 이상의 점이 찍혔을 때 '완료' 버튼 표시
  if (patrolAreaPoints.length >= 3) {
    document.getElementById("set-patrol-btn").classList.remove("hidden");
  }
  customAlert(`웨이포인트 ${patrolAreaPoints.length}개 지정됨.`);
};

// 캔버스에 점과 선을 그리는 함수 (시각화)
const drawPatrolArea = () => {
  const ctx = mapCanvas.getContext("2d");

  // 캔버스 클리어 (실제 지도 렌더링을 시뮬레이션하기 위해)
  ctx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);

  if (patrolAreaPoints.length > 0) {
    ctx.strokeStyle = "#ef4444"; // Red-500
    ctx.lineWidth = 4;
    ctx.fillStyle = "rgba(239, 68, 68, 0.2)"; // Red-500 투명

    ctx.beginPath();
    ctx.moveTo(patrolAreaPoints[0].x, patrolAreaPoints[0].y);

    for (let i = 1; i < patrolAreaPoints.length; i++) {
      ctx.lineTo(patrolAreaPoints[i].x, patrolAreaPoints[i].y);
    }

    // 폴리곤을 닫습니다. (시각적 피드백)
    if (patrolAreaPoints.length >= 2) {
      ctx.closePath();
      ctx.stroke();
    }

    // 각 웨이포인트(점)를 표시
    patrolAreaPoints.forEach((point) => {
      ctx.fillStyle = "#10b981"; // Green-500
      ctx.beginPath();
      ctx.arc(point.x, point.y, 8, 0, 2 * Math.PI); // 점 크기 8px
      ctx.fill();
    });
  }
};

// 구역 그리기 시작 버튼 클릭 시
window.startDrawingPatrolArea = function () {
  if (currentMainView !== "map") {
    customAlert("순찰 구역 설정은 지도(SLAM) 뷰에서만 가능합니다.");
    return;
  }
  // 그리기 모드 토글 (취소 기능 포함)
  if (isDrawingPatrolArea) {
    stopDrawingPatrolArea(true); // 취소 시 초기화
    return;
  }

  isDrawingPatrolArea = true;
  patrolAreaPoints = []; // 새롭게 그리기 시작

  mapContainer.classList.add("drawing-active");
  document
    .getElementById("draw-patrol-btn")
    .classList.replace("bg-purple-500", "bg-red-500");
  document.getElementById("draw-patrol-btn").innerHTML =
    '<i class="fas fa-times-circle mr-2"></i> 구역 그리기 취소';
  document.getElementById("set-patrol-btn").classList.add("hidden");
  document.getElementById("drawing-status").classList.remove("hidden");

  mapCanvas.addEventListener("click", handleMapClick);
  customAlert("지도 위를 클릭하여 순찰할 웨이포인트를 찍으세요.");
};

// 구역 그리기 모드 비활성화 및 초기화
const stopDrawingPatrolArea = (resetPoints = true) => {
  isDrawingPatrolArea = false;
  mapContainer.classList.remove("drawing-active");
  mapCanvas.removeEventListener("click", handleMapClick);

  document
    .getElementById("draw-patrol-btn")
    .classList.replace("bg-red-500", "bg-purple-500");
  document.getElementById("draw-patrol-btn").innerHTML =
    '<i class="fas fa-mouse-pointer mr-2"></i> 지도에 구역 그리기 시작';
  document.getElementById("set-patrol-btn").classList.add("hidden");
  document.getElementById("drawing-status").classList.add("hidden");

  if (resetPoints) {
    patrolAreaPoints = [];
    // 캔버스 오버레이 초기화
    mapCanvas
      .getContext("2d")
      .clearRect(0, 0, mapCanvas.width, mapCanvas.height);
  }
};

// 구역 설정 완료 및 명령 전송 (다음 단계 작업이 필요한 부분)
window.setPatrolArea = function () {
  if (patrolAreaPoints.length < 3) {
    customAlert(
      "최소 3개 이상의 웨이포인트를 지정해야 순찰 구역을 설정할 수 있습니다."
    );
    return;
  }

  customAlert("순찰 구역 설정 완료! 로봇에게 명령을 전송합니다.");
  stopDrawingPatrolArea(false);

  console.log("--- 순찰 구역 웨이포인트 (캔버스 픽셀 좌표) ---");
  patrolAreaPoints.forEach((p) =>
    console.log(`X: ${p.x.toFixed(2)}, Y: ${p.y.toFixed(2)}`)
  );

  // 🚨 다음 단계: 픽셀 좌표를 ROS 미터 좌표로 변환하고 ROS 토픽으로 발행하는 로직이 여기에 추가되어야 합니다.

  updateRobotStatus("순찰중");
};

// ====================================================================
// 로봇 제어 및 미션 명령
// ====================================================================

const cmdVel = new ROSLIB.Topic({
  ros: ros,
  name: "/cmd_vel",
  messageType: "geometry_msgs/Twist",
});

window.publishCommand = function (command) {
  if (!ros.isConnected) {
    customAlert("ROS 서버에 연결되어야 제어할 수 있습니다.");
    return;
  }

  if (currentMainView !== "video" && command !== "stop") {
    customAlert("수동 제어(방향키)는 웹캠 모드에서만 가능합니다.");
    return;
  }

  let linear = { x: 0.0, y: 0.0, z: 0.0 };
  let angular = { x: 0.0, y: 0.0, z: 0.0 };
  const speed = 0.4;
  const turn = 0.8;

  switch (command) {
    case "forward":
      linear.x = speed;
      break;
    case "backward":
      linear.x = -speed;
      break;
    case "left":
      angular.z = turn;
      break;
    case "right":
      angular.z = -turn;
      break;
    case "stop":
      updateRobotStatus("정지");
      const stopTwist = new ROSLIB.Message({
        linear: { x: 0.0, y: 0.0, z: 0.0 },
        angular: { x: 0.0, y: 0.0, z: 0.0 },
      });
      cmdVel.publish(stopTwist);
      console.log("Command: STOP");
      return;
    default:
      break;
  }

  const twist = new ROSLIB.Message({ linear: linear, angular: angular });
  cmdVel.publish(twist);
  console.log(`Manual Command: ${command}`);
};

window.publishMission = function (missionType) {
  if (!ros.isConnected) {
    customAlert("ROS 서버에 연결되어야 미션 명령을 보낼 수 있습니다.");
    return;
  }

  let alertMessage = "";
  let newStatus = "";

  switch (missionType) {
    case "return":
      alertMessage = "복귀 명령을 전송했습니다.";
      newStatus = "복귀중";
      break;
    case "repeat":
      alertMessage = "반복 순찰을 시작합니다.";
      newStatus = "순찰중";
      break;
    case "single":
      alertMessage = "1회 순찰을 시작합니다.";
      newStatus = "순찰중";
      break;
    default:
      return;
  }
  console.log(`Mission Command: ${missionType}`);
  updateRobotStatus(newStatus);
  customAlert(alertMessage);
};

// ====================================================================
// 커스텀 알림 및 초기화
// ====================================================================

window.customAlert = function (message) {
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = `<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                                    <div class="bg-white p-6 rounded-xl shadow-2xl max-w-md w-full">
                                        <p class="text-xl font-bold text-blue-600 mb-4 flex items-center"><i class="fas fa-info-circle mr-2"></i> 시스템 알림</p>
                                        <p class="text-gray-700 mb-6">${message}</p>
                                        <button onclick="this.closest('.fixed').remove()" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg w-full transition">확인</button>
                                    </div>
                                </div>`;
  document.body.appendChild(tempDiv);
};

// 페이지 로드 시 초기화
window.onload = function () {
  // 캔버스 크기 조정 (Tailwind CSS의 .w-full, .h-full이 적용된 후 실행되어야 합니다.)
  const container = mapCanvas.parentElement;
  mapCanvas.width = container.offsetWidth;
  mapCanvas.height = container.offsetHeight;

  ros.connect();
  toggleMainView("map");
  // isVideoRunning = false; 상태로 시작하며, 웹캠 버튼은 '시작' 상태를 보여줍니다.
};
