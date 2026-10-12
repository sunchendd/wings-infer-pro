# SecJ_Avoid_Print_Stack_Trace

- **规则ID**：155fe6ad-ffa7-467c-9dea-46727f0e6406
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

在日志中不能输出口令、密钥和其他敏感信息，口令包括明文口令和密文口令，敏感信息包括系统等隐私信息。

**【正确示例】**

```
public void test01Good() {
    try {
        int a = 5 / 0;
    } catch (Exception e) {
        LOG.info(e.getMessage());
    }
}

```
**【错误示例】**

```
public void test01Bad() {
    try {
        int a = 5 / 0;
    } catch (Exception e) {
        /* POTENTIAL FLAW: 当系统数据或调试信息通过输出流或者日志功能流出程序时，就会发生信息泄漏 */
        e.printStackTrace();
    }
}

```
**【修复建议】**

不要调用printStackTrace方法。
