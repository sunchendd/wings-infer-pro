# G.CTL.06 goto语句只能向下跳转

- **规则ID**：92bfcaf2-1830-4951-b06f-37ec3afdba0e
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

使用向上跳转的goto语句会导致代码可读性差、程序难以调试等问题。



因此，如果一定要使用goto语句，goto语句只能向下跳转。

**【正确示例】**

```
##### 场景1：使用向上跳转的goto语句
- 修复示例：
```c
void Func(void)
{
    int loopCnt = 0;

    while(loopCnt++) {
        if (loopCnt == MAX_COUNT) {
            goto LOOP2; // 符合：只能向下跳转
        }
        ...
    }
    ...

LOOP2:
    ...
}

```

```
**【错误示例】**

```
##### 场景1：使用向上跳转的goto语句
- 错误示例：
```c
void Func(void)
{
    int loopCnt = 0;

LOOP1:
    loopCnt++;
    if (loopCnt < MAX_COUNT) {
        goto LOOP1;     // 不符合：向上跳转
    } else {
        ...
    }
    ...

}

```

```
**【修复建议】**

1. 除了必须使用goto的场景（如在函数末尾进行错误处理）外，不应使用goto语句，可使用结构化的控制语句（如if、for、while等）来实现程序逻辑。

2. 必须使用goto的场景，goto语句不要向上跳转，只能向下跳转。
