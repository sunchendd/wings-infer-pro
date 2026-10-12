# DC.G.FUN.03 检查未使用的函数参数

- **规则ID**：14e96f78-b470-47d5-98a0-bedd6e1a606d
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

一般

**【描述】**

行号：xxx，列号：xxx：参数“xxx”未使用，可以删除

**【正确示例】**

```
```
local function foo(para) local total = get() local count = para + total return count end
```

```
**【错误示例】**

```
```
local function foo(para, data) 
    local total = get()
    local count = para + total
    return count
end
```

```
**【修复建议】**

未被使用的参数往往是因为设计发生了变动造成的，它可能导致传参时出现不正确的参数匹配
