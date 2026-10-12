# G.TYP.09 确保用key读取到map的元素有效

- **规则ID**：3164dca0-bf56-4877-ade9-be4052b9527d
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

严重

**【描述】**

从一个 map 中取一个不存在的 key，会返回该 map 的 value 类型的零值，取到的零值可能会导致程序出现异常或错误。

**【正确示例】**

```
##### 场景1：未判断用key读取到map的元素是否有效
- 修复示例1：使用多重赋值来分辨key不存在的情况。
    ```go
    // average 计算输入学生的平均年龄
    func (c class) average(students []name) (float32, error) {
        cnt := 0
        sum := age(0)
        for _, student := range students {
            if studentAge, ok := c[student]; !ok { // 符合：判断key对应的值存在
                continue
            } else {
                sum += studentAge
                cnt++
            }
        }
        if cnt == 0 {
            return 0, errors.New("input is empty or not found")
        }
        return float32(sum) / float32(cnt), nil
    }
    ```
- 修复示例2：对取得的零值做相应的异常处理。
    ```go
    // average 计算输入学生的平均年龄
    func (c class) average(students []name) (float32, error) {
        cnt := 0
        sum := age(0)
        for _, student := range students {
            studentAge := c.getAge(student)
            if studentAge == age(0) { // 符合：对取得的零值做异常处理
                continue
            }
            sum += studentAge
            cnt++
        }
        if cnt == 0 {
            return 0, errors.New("input is empty or not found")
        }
        return float32(sum) / float32(cnt), nil
    }
    ```


```
**【错误示例】**

```
##### 场景1：未判断用key读取到map的元素是否有效
- 错误示例：
    ```go
    type (
        age uint
        name string
        class map[name]age
    )

    func (c class) getAge(name name) age {
        return c[name] // 不符合：这里如果查找失败，缺省会返回0，造成外部计算错误
    }

    // average 计算输入学生的平均年龄
    func (c class) average(students []name) (float32, error) {
        if len(students) == 0 {
            return 0, errors.New("input is empty")
        }

        sum := age(0)
        for _, student := range students {
            sum += c.getAge(student)
        }
        return float32(sum) / float32(len(students)), nil
    }
    ```


```
**【修复建议】**

使用多重赋值来分辨key不存在的情况（即`"comma ok"`的方式判断是否正确获取到value）或者对取得的零值做相应的异常处理。
