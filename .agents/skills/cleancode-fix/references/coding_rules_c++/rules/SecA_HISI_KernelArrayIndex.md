# SecA_HISI_KernelArrayIndex

- **规则ID**：e336d815-ba65-49e0-a62d-429d34646f56
- **更新时间**：2025-03-25 19:23:54

---

**【问题级别】**

一般

**【描述】**

对外接口函数中,外部输入的数据未做校验直接作为数组的下标使用,导致数组越界读的风险。

**【正确示例】**

```
//right
int test2(int n) {
    int array[LENGTH] = { 0 };
 if(n >= LENGTH)
  return -1;
 
 array[n] = 10;
    return 0;
}

//right
int test3(int n) {
    int array[LENGTH] = { 0 };
 if(LENGTH <= n)
  return -1;
 
 array[n] = 10;
    return 0;
}

//right
int test5(int n) {
    int array[LENGTH] = { 0 };
 n = 6;
 
 array[n] = 10;
    return 0;
}

```
**【错误示例】**

```
#define LENGTH  100

//error
int test1(int n) {
    int array[LENGTH] = { 0 };
 array[n] = 10;

    return 0;
}

//wrong
int test4(int n) {
    int array[LENGTH] = { 0 };
 int m = n;
 
 array[m] = 10;
    return 0;
}

//error
int test6(int n) {
    int array[LENGTH] = { 0 };
 int *p = array;
 
 *(p + n) = 10;

    return 0;
}

```
**【修复建议】**

数组使用外部输入变量用作下标之前，需要进行校验
