# G.CTL.09 switch语句避免依赖隐式下沉

- **规则ID**：e8b89cfd-0e88-45ab-9851-8a32600f210c
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

每一个非空case语句应使用break结尾，避免出现由于意外遗漏break而导致的意外缺陷。

如果需要做下沉处理，应使用标识显式表示出来，如`fall-through`。

**【正确示例】**

```
##### 场景1：case语句中缺少break
- 修复示例：

```c
void GoodCase(int cond)
{
    int val = 10;
    switch (cond) {
        case 1:
            val++;
            /* fall-through */  // 符合：增加显式下沉标识
        case 2:
            val += 2;
            break;   // 符合：增加break
        default:
            val += 10;
            break;
    }
}
```


```
**【错误示例】**

```
##### 场景1：case语句中缺少break
- 错误示例：

```c
void BadCase(int cond)
{
    int val = 10;
    switch (cond) {
        case 1:
            val++;    // 不符合：缺少break也没有显式下沉标识
        case 2:
            val += 2; // 不符合：缺少break也没有显式下沉标识
        default:
            val += 10;
            break;
    }
}
```


```
**【修复建议】**

case语句块确认是否需要break，

1. 如果需要请增加break。

2. 如果不需要应使用下沉标识显式表示出来，如`fall-through`。
