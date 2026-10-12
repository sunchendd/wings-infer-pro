# G.FUN.01-03 函数最大代码嵌套深度必须小于等于:4

- **规则ID**：46ae32c0-d6d1-4276-84f5-5de4232ada78
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

一般

**【描述】**

行号：xxx 函数 xxx 的最大代码嵌套深度为 xx，按规范要求必须小于等于:5

**【正确示例】**

```
```
function func() 
    if !exp1 then
        ...
    end
    if exp2 then
        if exp3 then 
            if exp4 then
                ...
            end
        end
    end
end
```

```
**【错误示例】**

```
```
function func() 
    if exp1 then
        if exp2 then
            if exp3 then 
                if exp4 then
                    ...
                end
            end
        end
    end
end
```

```
**【修复建议】**

函数最大代码块嵌套深度。建议不超过 4 层
