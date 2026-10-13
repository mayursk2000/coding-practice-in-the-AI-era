import java.util.HashMap;
import java.util.Map;

public class LRUCache<K,V> {
    public static final class Node<K,V> {
        final K Key;
        V value;

        Node<K,V> prev;
        Node<K,V> next;

        Node(K key, V value) {
            this.Key = key;
            this.value = value;
        }



    }

    //node is defined, we come to the implementation

    private final int capacity;
    private final Map<K, Node<K,V>> map;

    private Node<K,V> head;
    private Node<K,V> tail;

    public LRUCache(int capacity) {

        if(capacity <= 0){
            throw new IllegalArgumentException("Capacity should be greater than 0");
        }
        this.capacity = capacity;
        this.map = new HashMap<>();

        this.head = new Node<>(null, null);
        this.tail = new Node<>(null, null);

        head.next = tail;
        tail.prev = head;
    }

    //get method
    public V get(K key) {
        Node<K,V> node = map.get(key);
        if(node == null){
            return null;
        }
        //move the node to the head of the list
        moveToHead(node);
        return node.value;
    }


    public void put(K key, V value) {
        Node<K,V> existing = map.get(key);

        if(existing != null){
            existing.value = value;
            moveToHead(existing);
            return;
        }

        Node<K,V> newNode = new Node<>(key, value);
        map.put(key, newNode);
        addtoHead(newNode);

        if(map.size() > capacity){
            evictLRU();
        }


    }


    //writing the delete method for the LRU cache
    public boolean delete(K key) {
        Node<K,V> node  =map.remove(key);

        if(node == null){
            return false;
        }
        removeNode(node);
        return true;
    }

    private void moveToHead(Node<K,V> node) {
        removeNode(node);
        addtoHead(node);
    }

    private void addtoHead(Node<K,V> node){
        Node<K,V> nextNode = head.next;
        head.next = node;
        node.prev = head;

        node.next = nextNode;
        nextNode.prev = node;
    }

    private void removeNode(Node<K, V> node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;

        node.prev = null;
        node.next = null;

    }

    private void evictLRU(){
        Node< K, V > victim = tail.prev;

        if(victim == head){
            return;
        }

        removeNode(victim);
        map.remove(victim.key);
    }
    
}