# G.ERR.03 包外可见的函数禁止向外抛出panic

- **规则ID**：a59fa443-2155-40b9-9eee-5d265556e48e
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

包外可见的函数如果向外抛出panic，可能会导致调用者意外退出。

因此，包外可见的函数禁止向外抛出panic，如果导出函数本身或其调用的函数可能抛出panic，需要内部recover并转换为error返回给包外调用者。

**【正确示例】**

```
##### 场景1：包外可见函数主动调用panic, 可能导致调用者被意外退出。
- 修复示例1：
    ```go
    package cube

    const MaxLen = 10

    type cube struct {
        length int
        width  int
        height int
    }
    func (c *cube) GetVolume() int {
        if c.isLessMaxLen() {
            return c.height * c.width * c.length
        } else {
            c.Reduce(MaxLen)
            return c.height * c.width * c.length
        }
    }
    // 在当前包中只可使用newCube的构建函数
    func NewCube(l, w, h int) *cube {
        if l < w {
            l, w = w, l
        }
        if l < h {
            l, h = h, l
        }
        return &cube{length: l, width: w, height: h}
    }
    func (c *cube) Increase(num int) {
        if c.length+num < MaxLen {
            c.height += num
            c.width += num
            c.length += num
        }
    }
    func (c *cube) Reduce(num int) {
        if c.length-num > 0 {
            c.height -= num
            c.width -= num
            c.length -= num
        }
    }
    func (c *cube) isLessMaxLen() bool {
        return c.length < MaxLen // 符合：使isLessMaxLen()功能单一
    }
    ```

```
**【错误示例】**

```
##### 场景1：包外可见函数主动调用panic, 可能导致调用者被意外退出。
- 错误示例：
    ```go
    package cube

    const MaxLen = 10

    type cube struct {
        length int
        width  int
        height int
    }

    func (c *cube) GetVolume() int {
        // 如果长度小于MAXLEN直接计算体积，否则长度回滚到原来长度再计算体积
        if c.isLessMaxLen() { // 不符合，包外可见函数调用了抛出panic的函数，且未处理
            return c.height * c.width * c.length
        } else {
        c.Reduce(MaxLen)
        return c.height * c.width * c.length
        }
    }
    func (c *cube) Increase(num int) {
        c.height += num
        c.width += num
        c.length += num
    }
    func (c *cube) Reduce(num int) {
        c.height -= num
        c.width -= num
        c.length -= num
    }
    func (c *cube) isLessMaxLen() bool {
        if c.length > MaxLen {
            panic("The length more than max width.")
        }
        return true
    }
    ```

```
**【修复建议】**

导出函数本身禁止向外抛出panic，如果导出函数本身或其调用的函数可能抛出panic，建议内部recover并转换为error返回给包外调用者。
