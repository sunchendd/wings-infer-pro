# DC.G.PRM.04 参数避免过多使用..检查(超过6次)

- **规则ID**：cd2a51b9-28c0-4a93-bcda-d75882ca2531
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：参数中连接符..使用超过6次，请调整

**【正确示例】**

```
```
local t = {} while true do local s = get_string() if s == nil then break end -- 假设循环次数较多 table.insert(t, s) end print(table.concat(t))
```

```
**【错误示例】**

```
```
local output = ""
while true do
    local s = get_string()
    if s == nil then break end -- 假设循环次数较多
    output = output .. s -- Bad: 用“..”循环拼接字符串
end
print(output)
```

```
**【修复建议】**

用“..”循环拼接字符串时，每次操作将生成一个新的字符串来保存拼接过程结果，在循环中拼接会影响效率，因此应避免使用“..”循环拼接字符串。
