# G.VAR.08 资源不再使用时应予以关闭或释放

- **规则ID**：38f3c252-f5bd-4b39-a042-ffd633f6e77a
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

跟踪变量的生命周期，在变量的生命周期结束之前，如果存在申请后没有释放的内存。产生告警。

**【正确示例】**

```
```
char* getBlock(int fd)
{
    char* buf = (char*)malloc(BLOCK_SIZE);
    if (!buf) {
        return nullptr;
    }
    if (read(fd, buf, BLOCK_SIZE) != BLOCK_SIZE) {
        free(buf)
        return nullptr;
    }
    return buf;
}
```

```
**【错误示例】**

```
```
char* getBlock(int fd)
{
    char* buf = (char*)malloc(BLOCK_SIZE);
    if (!buf) {
        return nullptr;
    }
    if (read(fd, buf, BLOCK_SIZE) != BLOCK_SIZE) {
        return nullptr;
    }
    return buf;
}
```

```
**【修复建议】**

检查所有的路径，对资源生命周期结束前的关闭或释放是否有遗漏
