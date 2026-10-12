# G.FUD.06 内联函数要尽可能短，避免超过10行

- **规则ID**：15794409-8d6d-460d-9a69-34fb18deb0ed
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

内联函数规模建议控制在 10 行（非空非注释）以内。

**【正确示例】**

```
##### 场景1：内联函数超过10行
- 修复示例：

```c
int MyFread(char *buf, int max) // 符合：改为非内联函数
{
    int c;
    int n = 0;

    while ((n < max) && ((c = getchar()) != EOF)) {
        *(buf++) = c;
        n++;
        if (c == '
' || c == '\r') {
            break;
        }
    }
    return n;
}
```

```
**【错误示例】**

```
##### 场景1：内联函数超过10行
- 错误示例：

```c
inline int MyFread(char *buf, int max) // 不符合：内联函数超过10行
{
    int c;
    int n = 0;

    while ((n < max) && ((c = getchar()) != EOF)) {
        *(buf++) = c;
        n++;
        if (c == '
' || c == '\r') {
            break;
        }
    }
    return n;
}
```

```
**【修复建议】**

拆分内联函数或者改为非内联函数。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
