# 安全TOP问题-不安全的SSL验证检查

- **规则ID**：c589b5cf-c94a-4a5f-9e9a-b513c1091ece
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

严重

**【描述】**

secBrella告警清理指导链接:http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&navid=NVI1000072714

不安全的SSL校验

**【正确示例】**

```
请参考清理指导链接

```
**【错误示例】**

```
WebView webView = new WebView(this);

webView.loadUrl("https://www.baidu.com");

Email email = new HtmlEmail();

try {
    /* POTENTIAL FLAW: Insecure SSL: Server Identity Verification Disabled */
    email.send();
} catch (EmailException e) {
   LOGGER.error("failed to send email.", e);
}

```
**【修复建议】**

不要放弃SSL的验证检查。
