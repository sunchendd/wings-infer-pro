# 安全TOP问题-内存泄漏检查

- **规则ID**：696f9688-53b3-44db-bc51-de879876a281
- **更新时间**：2025-03-25 19:24:03

---

**【问题级别】**

一般

**【描述】**

内存泄漏检查

**【正确示例】**

```
void GoodCase01()
{
    /* POTENTIAL FLAW GOOD:  */
    int *x = new int;
    // do something
    delete(x);
}

```
**【错误示例】**

```
void BadCase01()
{
    /* POTENTIAL FLAW:  */
    int *x = new int;
    // do something
    // 内存未释放
}

```
**【修复建议】**

程序员在创建或分配资源后，如果该资源不再被使用，程序员应将其正确的关闭或释放，尤其要注意所有可能的异常路径，避免遗漏。
