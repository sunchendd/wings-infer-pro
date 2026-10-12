# G.VAR.02-02 禁止无效的变量初始化和变量赋值

- **规则ID**：98eec38e-3a49-4fd7-8a15-bcfa89112fcb
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：变量"xxx"在"xxx"行赋值后，作用域结束前，在所有分支都无人读取

**【正确示例】**

```
```
function foo()
    local value   
    ...             
    return
end
```

```
**【错误示例】**

```
```
function foo()
    local value   
    ...          
    value = nil   
    return
end
```

```
**【修复建议】**

函数即将返回，value此处的赋值是无效的
