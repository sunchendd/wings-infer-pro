# G.VAR.02-01 禁止冗余的变量初始化和变量赋值

- **规则ID**：38ef189d-7dcb-4fec-b625-269856b08e94
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

进行冗余变量初始化和变量赋值

**【正确示例】**

```
```
local function foo()
    do_sth()
    local value = get_value(...) 
    ...
End
```

```
**【错误示例】**

```
```
local function foo()
    local value = 0     
    do_sth()
    value = get_value(...)
    ...
End
```

```
**【修复建议】**

不要进行冗余变量初始化和变量赋值
