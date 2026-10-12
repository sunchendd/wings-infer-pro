# G.FUN.04 返回已被修改大小的slice参数对象

- **规则ID**：b27b59a7-4588-4d1f-920d-d6691ac6eacd
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

slice的append操作有可能修改slice指向的地址。

因此，如果函数被设计用于更新传入的slice参数，则它的实现需要满足：如函数包含slice参数（而不是slice指针）并对其进行append操作，必须返回修改后的slice

**【正确示例】**

```
##### 场景1：参数slice经append后未返回
- 修复示例：函数包含slice参数（而不是slice指针）并对其进行append操作，必须返回修改后的slice。
    ```go
    func AppendXXXList(s []int) []int { // 符合： 返回slice，调用者负责更新slice实参的原版本（其中包含了旧的大小和地址）
        s[0] = 10 // 符合：只是修改内容但没有修改规模
        s2 := append(s, 11);  // 修改规模
        return s2 // 符合: 函数返回s
    }
    func main() {
        array := []int{1, 2, 3, 4, 5}
        array = AppendXXXList(array) // 符合：因为后面重用了array，需要重新给它赋值
        // 继续使用array，如下的打印，查看被修改的`slice`的内容
        // ...
        fmt.Println(array) // 打印结果为[10 2 3 4 5 11]
    }
    ```


```
**【错误示例】**

```
##### 场景1：参数slice经append后未返回
- 错误示例：下面代码直接对函数的slice类型入参进行处理，调用者期望入参是不受任何影响的，但实际上经过处理后，slice的值已发生变化。
    ```go
     func AppendXXXList(s []int) { // 不符合: 修改了slice的大小, 因而必须返回此slice
         s[0] = 10 // 符合: 只是修改内容但没有修改大小
         s = append(s, 11) // 修改大小，如函数不返回s则不符合规则
     }
     func main() {
         array := []int{1, 2, 3, 4, 5}
         AppendXXXList(array)
         // 继续使用array，如下的打印，查看被修改的slice的内容
         // ...
         fmt.Println(array) // 打印结果为[10 2 3 4 5], 不是期望的[10 2 3 4 5 11]
     }
    ```


```
**【修复建议】**

函数包含slice参数（而不是slice指针）并对其进行append操作，必须返回修改后的slice。
