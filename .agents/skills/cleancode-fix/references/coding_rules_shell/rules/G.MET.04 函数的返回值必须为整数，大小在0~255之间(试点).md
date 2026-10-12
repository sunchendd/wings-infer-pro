# G.MET.04 函数的返回值必须为整数，大小在0~255之间(试点)

- **规则ID**：bc9924b2-9dad-461e-b093-04990dcf18f6
- **更新时间**：2025-06-05 04:30:01

---

**【问题级别】**

严重

**【描述】**

Shell 函数返回值只能是整形数值，一般是用来表示函数执行成功与否的，0表示成功，其他值表示失

败。并且返回值的范围为0~255，超出此范围的整数会被截断。

**【正确示例】**

```
#!/bin/bash
  function my_func()
  {
  return 1
  }
  function my_func3()
  {
  echo "my_func3" 
  }
  result=$(my_func3)
  echo $result  # 此时打印 my_func3

```
**【错误示例】**

```
#!/bin/bash
  # 不符合：返回值必须是整型，并且返回值的范围为0~255
  function my_func1()
  {
  return -1 # -1会被截断为255
  }
  function my_func2()
  {
  return 300 # 300会被截断为44
  }
  function my_func3()
  {
  return "failed" # 执行出错：numeric argument required
  }
  my_func1

```
**【修复建议】**

- 返回值必须是整型，并且返回值的范围为0~255

- 如果函数想输出字符串，请使用标准输入输出
