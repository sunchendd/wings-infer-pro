# SecJ_Empty_Catch_Block

- **规则ID**：615ba1fa-3acd-42f0-8b74-50991644e7fc
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

未处理异常

**【正确示例】**

```
try {
    throwInterruptedException();
} catch (InterruptedException e) {
}

```
**【错误示例】**

```
try {
    throwException();
    /* POTENTIAL FLAW: catch 块可以处理的异常种类很多，但往往会由于过多的考虑不应该在此位置处理的各种问题或故障而困扰不已。 */
} catch (Exception e) {
}

```
**【修复建议】**

当捕获异常后，根据业务需要作出相应的处理，比如返回错误提示信息、使用日志记录异常信息等
