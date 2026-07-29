# Input Format

Ask the traveler for the smallest reliable brief:

```text
目的地：
开始日期：
结束日期：
节奏：轻松 / 标准 / 紧凑
兴趣：
必去：
避开：

攻略资料：粘贴正文、聊天记录或笔记。
攻略链接：每行一个公开网页或官方链接。

住宿：酒店名、地址、入住/退房日期、是否寄存行李。
交通：航班、高铁、火车、巴士或渡轮的出发地、到达地和时间。
主题：合集标题、署名、主色、封面图或 Logo（可选）。
```

Use public links only when the active environment can read them. For inaccessible pages, retain the URL as a low-confidence `sourceRecord` and ask the traveler to paste the relevant text or provide a screenshot. Do not imply that a social platform page was read when it was not.

From screenshots, keep only:

- hotel name, address, check-in and check-out;
- departure and arrival airport/station, date and time;
- terminal, platform, gate, baggage, boarding, or security notes;
- constraints that affect arrival, departure, or transfer buffers.

Never copy passenger names, booking references, QR codes, payment details, passport/ID numbers, phone numbers, or email addresses into the JSON or HTML.
