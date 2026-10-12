# SecA_HISI_KernelArrayIndex

- **规则ID**：9f84c450-e93f-493b-95c8-d0d8eece4bda
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

对外接口函数中,外部输入的数据未做校验直接作为数组的下标使用,导致数组越界读的风险。

**【正确示例】**

```
```
//good example

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

```
**【错误示例】**

```
```
//bad example

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

```
**【修复建议】**

数组使用外部输入变量用作下标之前，需要进行校验
