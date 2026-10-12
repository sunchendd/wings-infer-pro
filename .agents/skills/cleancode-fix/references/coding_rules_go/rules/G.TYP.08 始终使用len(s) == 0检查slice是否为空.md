# G.TYP.08 始终使用len(s) == 0检查slice是否为空

- **规则ID**：12d6fc00-0edd-445b-bae0-26fdb407ce55
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

严重

**【描述】**

若使用`slice == nil`检查slice是否为空（slice中没有元素），可能会导致检查结果错误。

如：`filtered := []int{}`，`filtered`为空，但是`filtered == nil`的值可能是false，判断结果不符合预期。

因此，必须使用`len(s) == 0`检查slice是否为空。

**【正确示例】**

```
##### 场景1：使用`s== nil`来检查slice是否为空，校验返回的结果可能错误
- 修复示例：

    ```go
    func isEmpty(s []string) bool {
        return len(s) == 0  // 符合
    }
    ```

```
**【错误示例】**

```
##### 场景1：使用`s== nil`来检查slice是否为空，校验返回的结果可能错误
- 错误示例：

    ```go
    func isEmpty(s []string) bool {
        return s == nil     // 不符合
    }
    ```

```
**【修复建议】**

使用`len(s) == 0`检查slice是否为空。
