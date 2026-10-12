# DC.G.PRM.01-02 spt相关函数资源释放检查

- **规则ID**：f2d8ea11-ab90-4d40-9760-d259778c0fce
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：函数“xxx”后未使用函数xxx释放handle

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
