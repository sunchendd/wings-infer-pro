# SecA_UninitAssign

- **规则ID**：19c9317e-86c7-4be3-9ce7-7ebad23e54fb
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

赋值操作中存在的未初始化变量问题

**【正确示例】**

```
void GoodCase() {
 int x = 8;
 /* POTENTIAL FLAW GOOD: left expression is initialized */
 x |= 1;
}

```
**【错误示例】**

```
void BadCase() {
 int x;
 /* POTENTIAL FLAW: left expression is uninitialized */
 x |= 1;
}

```
**【修复建议】**

变量使用前进行正确初始化
