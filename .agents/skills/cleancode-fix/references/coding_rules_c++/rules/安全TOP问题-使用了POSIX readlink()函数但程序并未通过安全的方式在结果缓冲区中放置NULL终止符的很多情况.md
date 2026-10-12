# 安全TOP问题-使用了POSIX readlink()函数但程序并未通过安全的方式在结果缓冲区中放置NULL终止符的很多情况

- **规则ID**：9c343d85-90a7-4f71-8985-128f45c270c2
- **更新时间**：2025-03-25 19:23:58

---

**【问题级别】**

严重

**【描述】**

调用readlink之后，需要检查确认返回值len不是-1并且该整数小于sizeof(buff)

**【正确示例】**

```
void ReadlinkGoodCase01()
{
    char filePath[128];
    int r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r != -1 && r < sizeof(filePath)) {
        /* POTENTIAL FLAW GOOD: */
        filePath[r] = '\0';
    }
}

```
**【错误示例】**

```
void ReadlinkBadCase01()
{
    char filePath[128];
    int r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r == -1) {
        return;
    }
    /* POTENTIAL FLAW: 没有检查readlink的返回值是否小于bufsize长度 */
    filePath[r] = '\0';
}
void ReadlinkBadCase02()
{
    char filePath[128];
    int r = readlink("some_file_path", filePath, sizeof(filePath));
    if (r == sizeof(filePath)) {
        return;
    }
    /* POTENTIAL FLAW: 没有检查readlink的返回值是否等于-1 */
    filePath[r] = '\0';
}

```
**【修复建议】**

正确使用readlink，检查确认返回值len 不是 -1 并且该整数小于sizeof(buff),确保获取的路径以'\0'结尾。
