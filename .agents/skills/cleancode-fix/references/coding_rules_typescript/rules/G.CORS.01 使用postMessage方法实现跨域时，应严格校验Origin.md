# G.CORS.01 使用postMessage方法实现跨域时，应严格校验Origin

- **规则ID**：694aa76c-0b27-42a2-ab0e-867accd6f015
- **更新时间**：2025-06-05 04:35:02

---

**【问题级别】**

一般

**【描述】**

HTML5增加了window.postMessage(message,targetOrigin,[transfer])方法，该方法可以实现跨域通信，以允许不同来源的Window对象之间进行消息交换。因为任何窗口都可以从其他窗口发送/接收消息，所以验证发送者/接收者的来源很重要，如果目标来源设置的过于宽松，恶意脚本就能趁机采用不当方式与受害者窗口进行通信，从而导致发送欺骗、数据被盗、转发及其他攻击。



因此，无论是作为消息的发送方还是接受方，都应该对目标源进行最小化校验，推荐使用白名单的方式，禁止使用indexOf()来校验目标源。

**【正确示例】**

```
var myWindow = document.getElementById('myIFrame'.contentWindow);
myWindow.postMessage(message,'https://example2.com');  // 该消息只能发送给https://example2.com的窗口

```
**【错误示例】**

```
// 发送方为https://example1.com页面的窗口，接收方为https://example2.com页面的窗口
var myWindow = document.getElementById('myIFrame'.contentWindow);
// 该消息可以发送到任何可以接受消息的窗口，不止https://example2.com页面的窗口
myWindow.postMessage(message,'*')；

```
**【修复建议】**

使用postMessage方法实现跨域时，应严格校验Origin
