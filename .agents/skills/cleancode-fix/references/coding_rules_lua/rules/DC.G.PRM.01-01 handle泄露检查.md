# DC.G.PRM.01-01 handle泄露检查

- **规则ID**：710486d8-aee3-4e47-9665-31e773e72f4e
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：代码块结束前没有释放句柄：“xxx”（存在资源泄露的风险）

**【正确示例】**

```
```
spt_Cquery;spt_EndQuery
spt_Query;spt_EndQuery
spt_AppQuery;spt_EndQuery
spt_BeginSelect;spt_EndSelect
spt_SelectAllRecCBuf;spt_FreeCBuf
spt_FetchRecCBuf;spt_FreeCBuf
spt_GetNextRecCBuf;spt_FreeCBuf
spt_AllocBlock;spt_FreeBlock
io.open;io.close
db:Open;db:Close
```

```
**【错误示例】**

```
```
local function foo()
    local ret, handle = spt_Query(cid, msgField, false)
    while true do
        ret, recCBuf = spt_GetNextRecCBuf(handle)
        if ret ~= OK then
            break
        end
        ... -- Bad: 代码块结束前没有释放buffer资源
    end
    return xxx -- Bad: 代码块结束前没有释放handle资源
end
```

```
**【修复建议】**

申请的资源使用完成后应及时释放，避免造成资源泄露。
