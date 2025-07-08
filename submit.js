let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1; // JSは0始まりなので+1

document.getElementById("prevMonthBtn").addEventListener("click", () => {
  changeMonth(-1);
});
document.getElementById("nextMonthBtn").addEventListener("click", () => {
  changeMonth(1);
});

const form = document.querySelector(".form");
const output = document.getElementById("output");
const tableArea = document.getElementById("workTableArea");

// 一覧表示のフォーム送信
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (output) output.textContent = "送信中...";

  const formData = new FormData(form);
  const data = {
    work_date: formData.get("work_date"),
    day_of_the_week: "",
    work_style: "出勤",
    start_time: formData.get("start_time"),
    end_time: formData.get("end_time"),
    break_time: "",
    work_time: "",
    note: ""
  };

  try {
    const response = await fetch("/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (response.ok) {
      if (output) output.innerHTML = `<div class="result">${result.message || "登録完了"}</div>`;
      renderTable(result.records || []);
    } else {
      if (output) output.innerHTML = `<div class="error">エラー: ${result.error}</div>`;
    }
  } catch (err) {
    if (output) output.innerHTML = `<div class="error">通信エラー: ${err.message}</div>`;
  }
});

// 勤怠一覧テーブル描画
function renderTable(records) {
  if (!records.length) {
    tableArea.innerHTML = "<p>表示するデータがありません。</p>";
    return;
  }

  let html = `<table border="1">
                <tr><th>日付</th><th>開始</th><th>終了</th></tr>`;
  for (const rec of records) {
    html += `<tr>
               <td>${rec.work_date || rec.date}</td>
               <td>${rec.start_time || rec.start}</td>
               <td>${rec.end_time || rec.end}</td>
             </tr>`;
  }
  html += "</table>";
  tableArea.innerHTML = html;
}

// 月切り替え
function changeMonth(offset) {
  currentMonth += offset;
  if (currentMonth < 1) {
    currentMonth = 12;
    currentYear -= 1;
  } else if (currentMonth > 12) {
    currentMonth = 1;
    currentYear += 1;
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
    note: ""
  };

  fetch("/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  })
    .then(res => res.json())
    .then(json => {
      if (json.records) renderTable(json.records);
    })
    .catch(err => {
      alert("送信エラー：" + err.message);
    });
}

// ダウンロードボタン処理
document.addEventListener("DOMContentLoaded", () => {
  const downloadBtn = document.getElementById("downloadBtn");
  if (!downloadBtn) {
    console.error("downloadBtn が見つかりません。HTMLのIDを確認してください。");
    return;
  }

  downloadBtn.addEventListener("click", async (e) => {
    e.preventDefault();

    console.log("ダウンロードボタン押下");

    // 表示中の月の1日をwork_dateに設定
    const work_date = `${currentYear}-${String(currentMonth).padStart(2, "0")}-01`;

    try {
      const response = await fetch("/download", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ work_date })
      });

      if (!response.ok) {
        throw new Error("ダウンロード失敗: " + response.status);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "attendance.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("ダウンロードエラー: " + err.message);
    }
  });
});