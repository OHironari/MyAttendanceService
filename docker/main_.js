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

// =====================
// 共通JSONパーサ
// =====================
async function parseLambdaResponse(res) {
  const raw = await res.json();
  let parsed = raw;
  if (typeof raw.body === "string") {
    try {
      parsed = JSON.parse(raw.body);
    } catch {
      throw new Error("parse_error");
    }
  }
  return parsed;
}

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
    style: "readonly",
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

    const result = await parseLambdaResponse(response);

    if (result?.error === "token expired") {
      localStorage.removeItem("id_token");
      redirectToLogin();
      return;
    }

    if (result && result.records && Array.isArray(result.records)) {
      renderTable(result.records);
    } else {
      tableArea.innerHTML = `<p style="color:red;">データが取得できませんでした。</p>`;
    }
  } catch (err) {
    if (err.message === "parse_error") {
      tableArea.innerHTML = `<p style="color:red;">サーバー応答解析エラー</p>`;
    } else {
      console.error("fetch error", err);
      tableArea.innerHTML = `<p style="color:red;">通信エラー: ${err.message}</p>`;
    }
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
  // const todayStr = new Date().toISOString().split("T")[0];
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0"); // 月は0始まり
  const day = String(now.getDate()).padStart(2, "0");
  const todayStr =  `${year}-${month}-${day}`;
  
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

    const todayClass = r.work_date === todayStr ? "highlight-today" : "";
    const alreadysubmit = r.submit === "1" ? "highlight-alreadysubmit" : "";

    html += `
      <tr data-date="${r.work_date}" class="${todayClass} ${alreadysubmit}">
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
  const submit = "1";
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
    submit,
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
    .then(parseLambdaResponse)
    .then(parsed => {
      if (parsed?.error === "token expired") {
        localStorage.removeItem("id_token");
        redirectToLogin();
        return;
      }
      if (parsed && parsed.records && Array.isArray(parsed.records)) {
        renderTable(parsed.records);
      } else {
        alert("不明なエラーが発生しました");
      }
    })
    .catch(err => {
      if (err.message === "parse_error") {
        alert("サーバー応答解析エラー");
      } else {
        alert("送信エラー：" + err.message);
      }
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
    const responses = await Promise.all([
      fetch("/download", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${idToken}`
        },
        body: JSON.stringify(data)
      }),
      fetch("/download2", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${idToken}`
        },
        body: JSON.stringify(data)
      })
    ]);

    // それぞれのレスポンスを処理
const results = await Promise.all(responses.map(async (res, i) => {
  const parsed = await parseLambdaResponse(res);
  if (parsed?.error === "token expired") {
    localStorage.removeItem("id_token");
    redirectToLogin();
    throw new Error("トークンの有効期限が切れました");
  }
  if (!parsed?.url) {
    throw new Error(`ファイル${i + 1}のURLが返されませんでした`);
  }
  return parsed.url;
}));

    // 署名付きURLのリンクを使ってダウンロード開始
for (const url of results) {
  const a = document.createElement("a");
  a.href = url;
  const filename = decodeURIComponent(url.split('/').pop().split('?')[0]);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  // 連続ダウンロードによるブロックを避ける
  await new Promise(resolve => setTimeout(resolve, 500));
}

  } catch (err) {
    console.error("ダウンロードエラー:", err);
    alert("ダウンロード中にエラーが発生しました:\n" + err.message);
  }
});

// =====================
// email 表示用関数追加
// =====================
function updateUserEmail() {
  const email = localStorage.getItem("email");
  let userEmailEl = document.getElementById("userEmail");
  if (!userEmailEl) {
    userEmailEl = document.createElement("div");
    userEmailEl.id = "userEmail";
    userEmailEl.style.position = "absolute";
    userEmailEl.style.top = "10px";
    userEmailEl.style.right = "20px";
    userEmailEl.style.color = "white";
    document.body.appendChild(userEmailEl);
  }
  if (email) {
    userEmailEl.textContent = email;
  }
}

window.onload = async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get("code");

  if (code) {
    try {
      const res = await fetch(`/auth?code=${code}`, { credentials: "include" });
      const data = await res.json();
      if (data.id_token && data.session_id && data.email) {
        localStorage.setItem("id_token", data.id_token);
        localStorage.setItem("email", data.email);
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
      updateUserEmail(); // ← ここで表示
      await fetchDataAndRender();
    }
  }
};

document.body.style.display = "none";

// Google Auth

document.getElementById("googleAuthBtn").addEventListener("click", () => {
  const clientId = "939083238703-qqb8jqn1lffbak5q3m709kh1808rptq7.apps.googleusercontent.com"; // googleのOAuthクライアントID
  const redirectUri = "https://app.itononari.xyz/gmailapi"; // Googleに設定したリダイレクトURI
  const scope = "https://www.googleapis.com/auth/gmail.compose";

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth` +
  `?client_id=${clientId}` +
  `&redirect_uri=${encodeURIComponent(redirectUri)}` +
  `&response_type=code` +
  `&scope=${encodeURIComponent(scope)}` +
  `&access_type=offline` +
  `&prompt=consent`; // consent を毎回表示（refresh_token取得のため）

  window.open(authUrl, "_blank");

});

