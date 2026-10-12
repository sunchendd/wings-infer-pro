# 安全TOP问题-可查找构造函数分配了内存并将其指针存储到对象字段中，但析构函数未释放内存的很多情况

- **规则ID**：bbe7217b-4ec3-439a-a3ab-430093438010
- **更新时间**：2025-03-25 19:23:50

---

**【问题级别】**

严重

**【描述】**

可查找构造函数分配了内存并将其指针存储到对象字段中，但析构函数未释放内存的很多情况。



**【正确示例】**

```
``` cpp
class  FrameworkListener4 {
    int *ps;
public:
    FrameworkListener4() {
        init(); //ok
    }
    FrameworkListener4(int *p) {
        ps = p;
        init(); //ok
    }
    FrameworkListener4(const FrameworkListener4 &e) {
        init();//ok
    }
    void init() {
        ps = new int[100];
    }
    ~FrameworkListener4(){
        delete[] ps;
    } 
};
```


```
**【错误示例】**

```
``` cpp
class  FrameworkListener {
    int *ps;
public:
    FrameworkListener() {
        /* POTENTIAL FLAW:  leak */
        init();//error
    }
    FrameworkListener(int *p) {
        /* POTENTIAL FLAW:  leak */
        init();//error
    }
    FrameworkListener(const FrameworkListener &e) {
        /* POTENTIAL FLAW:  leak */
        init();//error
    }
    void init() {
        ps = new int[10];
    }
};
```


```
**【修复建议】**

 构造函数分配了内存并将其指针存储到对象字段中，析构函数中要及时释放内存。
