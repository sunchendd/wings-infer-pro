# SecA_MisUseStrcats

- **规则ID**：5ba0d51c-8f59-4305-954d-82c9bffb9390
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

安全函数不正确使用：strcat_s/strncat_s第二个参数应该填写目的缓冲区原始真实大小，而不是剩余空间大小

**【正确示例】**

```
```
strncat_s(RequestHeader, sizeof(RequestHeader), "Connection: close", 17)
```

```
**【错误示例】**

```
```
strncat_s(RequestHeader, sizeof(RequestHeader), "Connection", 10)
strncat_s(RequestHeader, sizeof(RequestHeader)-10, "Connection: close", 17)
```

```
**【修复建议】**

正确填入目的缓冲区原始真实大小
