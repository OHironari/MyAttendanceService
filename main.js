const clientId = "2fcjlhtdstq0fd3nnvp6hnk1md";
const domain = "auth.itononari.xyz";
const redirectUri = "https://app.itononari.xyz/auth";
const scope = "openid+email";
const responseType = "code";

function redirectToLogin() {
  const loginUrl = `https://${domain}/login?client_id=${clientId}&response_type=${responseType}&scope=${scope}&redirect_uri=${redirectUri}`;
  window.location.href = loginUrl;
}

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;

const monthTitle = document.getElementById("monthTitle");
const tableArea = document.getElementById("workTableArea");
const totalWorkTimeEl = document.getElementById("totalWorkTime");
const form = document.querySelector(".form");

function updateMonthTitle() {
  monthTitle.textContent = `${currentYear}年${String(currentMonth).padStart(2, "0")}月`;
}

updateMonthTitle();

document.getElementById("prevMonthBtn").addEventListener("click", () => {
  changeMonth(-1);
});
document.getElementById("nextMonthBtn").addEventListener("click", () => {
  changeMonth(1);
});
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetchDataAndRender();
});

async function fetchDataAndRender() {
  let idToken = localStorage.getItem("id_token");
  if (!idToken) {
    redirectToLogin();
    return;
  }

  const newDateStr = `${currentYear}-${String(currentMonth).padStart(2, "0")}-01`;
  const data = {
    work_date: newDateStr,
    day_of_the_week: "",
    work_style: "出勤",
    start_time: "",
    end_time: "",
    break_time: "",
    work_time: "",
    note: "",
    id_token: idToken
  };

  try {
    const response = await fetch("/submit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${idToken}`
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();
    if (result.error === "token expired") {
      localStorage.removeItem("id_token");
      redirectToLogin();
      return;
    }

    if (result.records) {
      renderTable(result.records);
    } else {
      tableArea.innerHTML = `<p style="color:red;">データが取得できませんでした。</p>`;
    }
  } catch (err) {
    tableArea.innerHTML = `<p style="color:red;">通信エラー: ${err.message}</p>`;
  }
}

function renderTable(records) {
  if (!records.length) {
    tableArea.innerHTML = "<p>まだ勤怠データがありません。</p>";
    totalWorkTimeEl.textContent = "実働合計：00:00";
    return;
  }

  let html = `<table border="1">
    <thead>
      <tr>
        <th>日付</th><th>曜日</th><th>在宅/勤務</th><th>開始</th><th>終了</th>
        <th>休憩</th><th>実動</th><th>備考</th><th>操作</th>
      </tr>
    </thead><tbody>`;

  let totalMinutes = 0;
   const todayStr = new Date().toISOString().split("T")[0]; // "2025-07-15"

  for (const r of records) {
    let dayClass = "";
    if (r.day_of_the_week === "Sat") dayClass = "sat";
    else if (r.day_of_the_week === "Sun") dayClass = "sun";

    const dateParts = r.work_date.split("-");
    const displayDate = `${dateParts[1]}/${dateParts[2]}`;

    if (r.work_time && /^\d+:\d+$/.test(r.work_time)) {
      const [h, m] = r.work_time.split(":").map(Number);
      totalMinutes += h * 60 + m;
    }

    // 今日の場合は highlight クラスを追加
    const todayClass = r.work_date === todayStr ? "highlight-today" : "";

    html += `
      <tr data-date="${r.work_date}" class="${todayClass}">
        <td>${displayDate}</td>
        <td class="${dayClass}">${r.day_of_the_week || ""}</td>
        <td>
          <select name="work_style">
            <option value="出勤" ${r.work_style === "出勤" ? "selected" : ""}>出勤</option>
            <option value="出張" ${r.work_style === "出張" ? "selected" : ""}>出張</option>
            <option value="在宅" ${r.work_style === "在宅" ? "selected" : ""}>在宅</option>
            <option value="休み" ${r.work_style === "休み" ? "selected" : ""}>休み</option>
          </select>
        </td>
        <td><input type="time" name="start_time" value="${r.start_time || ''}" /></td>
        <td><input type="time" name="end_time" value="${r.end_time || ''}" /></td>
        <td><input type="time" name="break_time" value="${r.break_time || ''}" /></td>
        <td>${r.work_time || ''}</td>
        <td><input type="text" name="note" value="${r.note || ""}" /></td>
        <td><button type="button" class="submit-btn">Submit</button></td>
      </tr>`;
  }

  html += "</tbody></table>";
  tableArea.innerHTML = html;

  const buttons = tableArea.querySelectorAll(".submit-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      submitRow(btn);
    });
  });

  const totalHours = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
  const totalMins = String(totalMinutes % 60).padStart(2, "0");
  totalWorkTimeEl.textContent = `実働合計：${totalHours}:${totalMins}`;
}

function changeMonth(delta) {
  currentMonth += delta;
  if (currentMonth <= 0) {
    currentMonth = 12;
    currentYear -= 1;
  } else if (currentMonth >= 13) {
    currentMonth = 1;
    currentYear += 1;
  }

  updateMonthTitle();
  fetchDataAndRender();
}

function submitRow(button) {
  const row = button.closest("tr");
  const work_date = row.dataset.date;
  const day_of_the_week = row.cells[1].innerText;
  const work_style = row.querySelector('select[name="work_style"]').value;
  const start_time = row.querySelector('input[name="start_time"]').value;
  const end_time = row.querySelector('input[name="end_time"]').value;
  const break_time = row.querySelector('input[name="break_time"]').value;
  const note = row.querySelector('input[name="note"]').value;

  const idToken = localStorage.getItem("id_token");
  if (!idToken) {
    redirectToLogin();
    return;
  }

  const data = {
    work_date,
    day_of_the_week,
    work_style,
    start_time,
    end_time,
    break_time,
    work_time: "",
    note,
    id_token: idToken
  };

  fetch("/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${idToken}`
    },
    body: JSON.stringify(data)
  })
    .then(res => res.json())
    .then(json => {
      if (json.error === "token expired") {
        localStorage.removeItem("id_token");
        redirectToLogin();
        return;
      }
      alert("送信完了");
      if (json.records) renderTable(json.records);
    })
    .catch(err => {
      alert("送信エラー：" + err.message);
    });
}
window.submitRow = submitRow;

document.getElementById("downloadBtn").addEventListener("click", async (e) => {
  e.preventDefault();

  const idToken = localStorage.getItem("id_token");
  if (!idToken) {
    redirectToLogin();
    return;
  }

  const work_date = `${currentYear}-${String(currentMonth).padStart(2, "0")}-01`;
  const data = {
    work_date,
    id_token: idToken
  };

  try {
    const response = await fetch("/download", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${idToken}`
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();
    if (result.error === "token expired") {
      localStorage.removeItem("id_token");
      redirectToLogin();
      return;
    }

    const a = document.createElement("a");
    a.href = result.url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

  } catch (err) {
    alert("エラー: " + err.message);
  }
});

window.onload = async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get("code");

  if (code) {
    try {
      const res = await fetch(`/auth?code=${code}`, { credentials: "include" });
      const data = await res.json();
      if (data.id_token && data.session_id) {
        localStorage.setItem("id_token", data.id_token);
        window.location.replace(redirectUri);
        return;
      } else {
        alert("認証情報の取得に失敗しました");
      }
    } catch (err) {
      console.error("認証エラー:", err);
      alert("認証通信エラー");
    }
  } else {
    let idToken = localStorage.getItem("id_token");
    if (!idToken) {
      redirectToLogin();
    } else {
      document.body.style.display = "block";
      await fetchDataAndRender();
    }
  }
};

document.body.style.display = "none";