# G.CORS.01 使用postMessage方法实现跨域时，应严格校验Origin

- **规则ID**：95ffbe2a-7845-4032-b347-6b5555134df6
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

一般

**【描述】**

HTML5增加了window.postMessage(message,targetOrigin,[transfer])方法，该方法可以实现跨域通信，以允许不同来源的Window对象之间进行消息交换。因为任何窗口都可以从其他窗口发送/接收消息，所以验证发送者/接收者的来源很重要，如果目标来源设置的过于宽松，恶意脚本就能趁机采用不当方式与受害者窗口进行通信，从而导致发送欺骗、数据被盗、转发及其他攻击。



因此，无论是作为消息的发送方还是接受方，都应该对目标源进行最小化校验，推荐使用白名单的方式，禁止使用indexOf()来校验目标源。

**【正确示例】**

```
function good001(){
    let url=document.getElementById("targetURL").value
    if( whitelistVerification(url) ){
     window.postMessage("wwx1134524",url);
    }
}

```
**【错误示例】**

```
function bad001(){
    window.postMessage("wwx1134524","*");
}

```
**【修复建议】**

谨慎使用postMessage方法实现跨域
