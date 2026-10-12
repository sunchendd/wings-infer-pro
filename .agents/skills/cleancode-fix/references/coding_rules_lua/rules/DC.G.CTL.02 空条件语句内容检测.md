# DC.G.CTL.02 空条件语句内容检测

- **规则ID**：2cec54f7-813c-4906-a179-d1bc609c6246
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：条件语句中xxx行为空语句，无有效代码

**【正确示例】**

```
```
local function foo()
    ...

    if rec == nil then
        return
    end
    ...

    if id > max_id then
        proc_error()
    else
        bar()
    end
    ...

    if result == OK then
        bar()
    else
        proc_error()
    end
    ...
end
```

```
**【错误示例】**

```
```
local function foo()
    ...

    if rec == nil then
    end -- Bad: 分支没有执行任何实质处理
    ...

    if id > max_id then
    else -- Bad: 条件成立分支没有执行任何实质处理
        bar()
    end
    ...

    if result == OK then
        bar()
    else -- Bad：条件不成立分支没有执行任何实质处理
    end
    ...
end
```

```
**【修复建议】**

应合理设计条件语句，避免使用空条件语句，以使代码更简洁
